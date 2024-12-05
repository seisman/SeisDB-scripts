"""
Helper functions.
"""

from pathlib import Path

import pandas as pd
import numpy as np
from obspy.core.event import Event, Magnitude, Origin
from obspy import Catalog, UTCDateTime, read_events
from obspy.clients.fdsn.mass_downloader import Domain
from obspy.geodetics import gps2dist_azimuth, kilometers2degrees
from obspy.clients.fdsn.mass_downloader import MassDownloader, Restrictions
from obspy.taup import TauPyModel


def to_obspy_event(time, longitude, latitude, depth, magnitude) -> Event:
    """
    Create an ObsPy Event object from event information.

    depth is in km.
    """
    origin = Origin(
        time=UTCDateTime(time),
        longitude=longitude,
        latitude=latitude,
        depth=depth * 1000.0,  # ObsPy uses depth in meters.
    )
    magnitude = Magnitude(mag=magnitude)
    return Event(origins=[origin], magnitudes=[magnitude])


def read_events_from_csv(filename: str) -> Catalog:
    """
    Read events from a CSV file.

    The CSV file should contain the following columns:

    time, longitude, latitude, depth, magnitude
    """
    df = pd.read_csv(filename)

    cat = Catalog()
    for _, row in df.iterrows():
        cat.append(
            to_obspy_event(
                time=row["time"],
                longitude=row["longitude"],
                latitude=row["latitude"],
                depth=row["depth"],
                magnitude=row["magnitude"],
            )
        )
    return cat


def read_catalog(filename: str) -> Catalog:
    """
    Read a catalog from a QuakeML file or a CSV file.
    """
    match Path(filename).suffix.lower():
        case ".quakeml" | ".xml":
            return read_events(filename)
        case ".csv":
            return read_events_from_csv(filename)
        case _:
            msg = f"Unrecognized catalog format: {filename}."
            raise ValueError(msg)


class ComplexDomain(Domain):
    """
    A custom domain to select stations based on multiple criteria.

    - Rectangular domain with min/max latitude/longitude in degrees.
    - Circular domain with a center point and min/max radius in degrees.

    Parameters
    ----------
    minlatitude
        The minimum latitude in degrees.
    maxlatitude
        The maximum latitude in degrees.
    minlongitude
        The minimum longitude in degrees.
    maxlongitude
        The maximum longitude in degrees.
    latitude
        The latitude of the center point in degrees.
    longitude
        The longitude of the center point in degrees.
    minradius
        The minimum radius in degrees.
    maxradius
        The maximum radius in degrees.
    """

    def __init__(
        self,
        minlatitude: float | None = None,
        maxlatitude: float | None = None,
        minlongitude: float | None = None,
        maxlongitude: float | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        minradius: float | None = None,
        maxradius: float | None = None,
    ):
        # Rectangular domain with min/max latitude/longitude in degrees.
        self.minlatitude = minlatitude
        self.maxlatitude = maxlatitude
        self.minlongitude = minlongitude
        self.maxlongitude = maxlongitude
        # Circular domain with minradius and maxradius in degrees.
        self.latitude = latitude
        self.longitude = longitude
        self.minradius = minradius
        self.maxradius = maxradius

        # Rectangle and/or circular domain?
        self.rectangle_domain = False
        self.circle_domain = False
        if all(
            v is not None
            for v in [minlatitude, maxlatitude, minlongitude, maxlongitude]
        ):
            self.rectangle_domain = True
        if all(v is not None for v in [latitude, longitude, minradius, maxradius]):
            self.circle_domain = True

    def get_query_parameters(self) -> dict[str, float]:
        """
        Return the query parameters for the domain used by get_stations().

        The returned query parameters must be a rectangular domain or a circular domain,
        not both.

        When both rectangular and circular domains are specified, the rectangle domain
        will be used as the query parameters of the FDSN web services. The circular
        domain will be processed in the ``is_in_domain`` function.
        """
        if self.rectangle_domain:
            return {
                "minlatitude": self.minlatitude,
                "maxlatitude": self.maxlatitude,
                "minlongitude": self.minlongitude,
                "maxlongitude": self.maxlongitude,
            }
        if self.circle_domain:
            return {
                "latitude": self.latitude,
                "longitude": self.longitude,
                "minradius": self.minradius,
                "maxradius": self.maxradius,
            }
        return {}

    def is_in_domain(self, latitude: float, longitude: float) -> bool:
        """
        Return True if the given latitude and longitude are in the domain.

        This function is used to refine the domain after the data has been downloaded.
        """
        # Possible cases:
        #
        # 1. rectangular domain only: already processed by get_query_parameters()
        # 2. circular domain only: already processed by get_query_parameters()
        # 3. rectangular and circular domain: rectangular domain is used for
        #    get_query_parameters(), circular domain is used for is_in_domain()
        # 4. no domain: i.e., global doamin, return True
        if self.rectangle_domain and self.circle_domain:
            gcdist = kilometers2degrees(
                gps2dist_azimuth(self.latitude, self.longitude, latitude, longitude)[0]
                / 1000.0
            )
            return bool(self.minradius <= gcdist <= self.maxradius)
        return True


def event_get_waveforms(
    event: Event,
    minradius: float = 0.0,
    maxradius: float = 180.0,
    startrefphase: str | None = None,
    endrefphase: str | None = None,
    startoffset: float = 0.0,
    endoffset: float = 0.0,
    radius_step: float = 30.0,
    model: str = "iasp91",
    providers: list[str] | None = None,
    restriction_kwargs: dict = {},
):
    """
    Get waveforms for an event from multiple data centers via the FDSN web services.

    Parameters
    ----------
    event
        The Event object for which to download the waveforms.
    minradius
        The minimum radius for stations away from the epicenter in degrees.
    maxradius
        The maximum radius for stations away from the epicenter in degrees.
    startrefphase
        The reference phase to use for the start time. None means the origin time.
    endrefphase
        The reference phase to use for the end time. None means the origin time.
    startoffset
        The time in seconds to add to the start time.
    endoffset
        The time in seconds to add to the end time.
    providers
        List of FDSN client names or service URLS. None means all available clients.
    """
    origin = event.preferred_origin() or event.origins[0]  # event origin
    eventid = origin.time.strftime("%Y%m%d%H%M%S")  # event ID based on origin time

    mseed_storage = (
        f"mseed/{eventid}/"
        + "{network}.{station}.{location}.{channel}__{starttime}__{endtime}.mseed"
    )
    stationxml_storage = f"stations/{eventid}/" + "{network}.{station}.xml"

    domains, restrictions = [], []
    if not startrefphase and not endrefphase:
        # Reference phases are not given. Use origin time.
        domain = ComplexDomain(
            latitude=origin.latitude,
            longitude=origin.longitude,
            minradius=minradius,
            maxradius=maxradius,
        )
        restriction = Restrictions(
            starttime=origin.time + startoffset,
            endtime=origin.time + endoffset,
            **restriction_kwargs,
        )
        domains.append(domain)
        restrictions.append(restriction)
    elif startrefphase and endrefphase:
        # Reference phases are given. Use the reference phases.
        model = TauPyModel(model=model)
        for radius in np.arange(0, 181, radius_step):  # loop over epicentral distances
            if radius + radius_step < minradius or radius > maxradius:
                continue
            phasetime = model.get_travel_times(
                source_depth_in_km=origin.depth / 1000.0,
                distance_in_degree=max(radius, minradius),
                phase_list=startrefphase,
            )[0].time
            starttime = origin.time + phasetime + startoffset
            phasetime = model.get_travel_times(
                source_depth_in_km=origin.depth / 1000.0,
                distance_in_degree=min(radius + radius_step, maxradius),
                phase_list=endrefphase,
            )[-1].time
            endtime = origin.time + phasetime + endoffset

            domain = ComplexDomain(
                latitude=origin.latitude,
                longitude=origin.longitude,
                minradius=max(radius, minradius),
                maxradius=min(radius + radius_step, maxradius),
            )
            restriction = Restrictions(
                starttime=starttime, endtime=endtime, **restriction_kwargs
            )
            domains.append(domain)
            restrictions.append(restriction)
    else:
        msg = "startrefphase and endrefphase must be either both or neither."
        raise ValueError(msg)

    mdl = MassDownloader(providers=providers)
    for domain, restriction in zip(domains, restrictions):
        mdl.download(
            domain,
            restriction,
            mseed_storage=mseed_storage,
            stationxml_storage=stationxml_storage,
        )
