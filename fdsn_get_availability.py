"""
Get the data availability of seismic stations from FDSN data centers.

A seismic network or station may start in 1960 but only data since 2000 are available
from FDSN seismic data centers. This script can get the data availability of seismic
stations from FDSN data centers.

Also see a related ObsPy feature request: https://github.com/obspy/obspy/pull/3002

- Author: Dongdong Tian @ CUG
- Repository: https://github.com/seisman/SeisDB-scripts/
- History:
  - 2023/10/11 Initial version.
"""

import sys
from io import StringIO

import pandas as pd
import requests


def usage():
    """
    Print usage information.
    """
    print(
        "Get the data availability of seismic stations from FDSN data centers.\n\n"
        f"Usage:\n    python {sys.argv[0]} network station\n\n"
        "    'network'/'station' can be a single name, a comma-separated list of \n"
        "    names or a wildcard expression. For a wildcard expression, enclose it \n"
        "    in quotes.\n\n"
        f"Example:\n    python {sys.argv[0]} IM 'TX*'\n"
        ""
    )


if len(sys.argv) != 3:
    usage()
    sys.exit(1)

network, station = sys.argv[1], sys.argv[2]
r = requests.get(
    "https://service.iris.edu/fdsnws/availability/1/extent",
    params={"net": network, "sta": station, "format": "request"},
    timeout=30,
)
if r.status_code != 200:
    print(f"Error: {r.status_code}")
    sys.exit(1)

df = pd.read_csv(
    StringIO(r.text),
    names=["network", "station", "location", "channel", "starttime", "endtime"],
    sep=r"\s+",
)
df["starttime"] = pd.to_datetime(df["starttime"])
df["endtime"] = pd.to_datetime(df["endtime"])
print("Data availability:")
print(f"  network: {network}")
print(f"  station: {station}")
print("  Start time:", df["starttime"].min().strftime("%Y-%m-%d"))
print("  End time:", df["endtime"].max().strftime("%Y-%m-%d"))
