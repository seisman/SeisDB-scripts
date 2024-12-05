"""
Download seismic waveforms from multiple data centers via the FDSN web services.

This script extends ObsPy's MassDownloader module to allow more flexible data selection
and downloading.

Author:
    Dongdong Tian @ CUG (dtian@cug.edu.cn)
Revision History:
    2023/05/12    Initial version.
    2023/08/15    Support reading catalog from a CSV file.
    2023/08/15    Support selecting FDSN data centers.
    2024/12/05    Refactor to move functions into separate files.
"""

import sys

from helpers import event_get_waveforms, read_catalog


if len(sys.argv) == 1:
    sys.exit(f"Usage: python {sys.argv[0]} catalog.quakeml/catalog.csv")

cat = read_catalog(sys.argv[1])

for ev in cat:
    event_get_waveforms(
        ev,
        minradius=0.0,
        maxradius=90.0,
        startrefphase=["ttp"],
        endrefphase=["ttp"],
        startoffset=-120,
        endoffset=1800.0,
        radius_step=30.0,
        model="iasp91",
        providers=["IRIS"],
        restriction_kwargs=dict(
            reject_channels_with_gaps=False,
            minimum_length=0.9,
            minimum_interstation_distance_in_m=100.0,
            channel_priorities=("BH?", "HH?", "SH?"),
            sanitize=False,
        ),
    )
