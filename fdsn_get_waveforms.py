"""
Download seismic wavefroms from multiple data centers using ObsPy's MassDownloader.

- Author: Dongdong Tian @ CUG
- Repository: https://github.com/seisman/SeisDB-scripts/
- History:
    - 2023/10/16 Initial version.

Reference: https://docs.obspy.org/packages/autogen/obspy.clients.fdsn.mass_downloader.html
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

# Distance range in degrees
minradius, maxradius = 0.0, 90.0
# Time range relative to event origin time
startshift, endshift = 0.0, 1800.0


def event_get_waveforms(event):
    # Event origin
    origin = event.preferred_origin() or event.origins[0]
    eventid = origin.time.strftime("%Y%m%d%H%M%S")
    # Circular domain
    domain = CircularDomain(
        latitude=origin.latitude,
        longitude=origin.longitude,
        minradius=minradius,
        maxradius=maxradius,
    )

    # Restrictions
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
