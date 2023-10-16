"""
Download seismic wavefrom from multiple data centers using ObsPy's MassDownloader.
"""

import sys

from obspy import read_events
from obspy.clients.fdsn.mass_downloader import (
    CircularDomain,
    MassDownloader,
    Restrictions,
)

if len(sys.argv) != 2:
    print(f"Usage: python {sys.argv[0]} catalog.xml")
    sys.exit(1)

cat = read_events(sys.argv[1])

minradius = 0.0
maxradius = 90.0
startshift = 0.0
endshift = 1800


def event_get_waveforms(event):
    # event origin
    origin = event.preferred_origin() or event.origins[0]
    eventid = origin.time.strftime("%Y%m%d%H%M%S")
    # domain
    domain = CircularDomain(
        latitude=origin.latitude,
        longitude=origin.longitude,
        minradius=minradius,
        maxradius=maxradius,
    )

    # restrictions
    restrictions = Restrictions(
        starttime=origin.time + startshift,
        endtime=origin.time + endshift,
        reject_channels_with_gaps=False,
        minimum_length=0.5,
        minimum_interstation_distance_in_m=10e3,
        channel_priorities=[
            "BH[ZNE12]",
            "HH[ZNE12]",
            "EH[ZNE12]",
            "SH[ZNE12]",
            "LH[ZNE12]",
        ],
    )

    mseed_storage = (
        f"mseed/{eventid}/"
        + "{network}.{station}.{location}.{channel}__{starttime}__{endtime}.mseed"
    )
    stationxml_storage = f"stations/{eventid}/" + "{network}.{station}.xml"

    mdl = MassDownloader()
    mdl.download(
        domain,
        restrictions,
        mseed_storage=mseed_storage,
        stationxml_storage=stationxml_storage,
    )


for event in cat:
    event_get_waveforms(event)
