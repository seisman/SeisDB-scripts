"""
Helper functions.
"""
import pandas as pd
from obspy import Catalog, UTCDateTime
from obspy.core.event import Event, Magnitude, Origin


def read_events_from_csv(csvfile):
    """
    Read events from a CSV file.

    The CSV file should contain the following columns:

    - time
    - longitude
    - latitude
    - depth (in km)
    - magnitude

    Parameters
    ----------
    csvfile : str
        Path to CSV file.

    Returns
    -------
    cat : obspy.Catalog
        Catalog of events.
    """
    df = pd.read_csv(csvfile)
    cat = Catalog()
    for _, row in df.iterrows():
        origin = Origin(
            time=UTCDateTime(row["time"]),
            longitude=row["longitude"],
            latitude=row["latitude"],
            depth=row["depth"] * 1000.0,  # obspy expects depth in meters
        )
        magnitude = Magnitude(mag=row["magnitude"])
        event = Event(origins=[origin], magnitudes=[magnitude])
        cat.append(event)
    return cat
