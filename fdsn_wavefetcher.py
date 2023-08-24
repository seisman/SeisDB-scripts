from obspy.clients.fdsn import RoutingClient
import pandas as pd
from obspy import Catalog, UTCDateTime, read_events
from obspy.core.event import Event, Magnitude, Origin
from obspy.taup import TauPyModel
from obspy.geodetics import gps2dist_azimuth, kilometers2degrees, locations2degrees


def read_events_from_csv(filename):
    """
    Read events from a CSV file.

    The CSV file should contain the following columns:

    - time
    - longitude
    - latitude
    - depth (in km)
    - magnitude
    """
    df = pd.read_csv(filename)
    cat = Catalog()
    for _, row in df.iterrows():
        origin = Origin(
            time=UTCDateTime(row["time"]),
            longitude=row["longitude"],
            latitude=row["latitude"],
            depth=row["depth"] * 1000.0,
        )
        magnitude = Magnitude(mag=row["magnitude"])
        event = Event(origins=[origin], magnitudes=[magnitude])
        cat.append(event)
    return cat

client = RoutingClient("iris-federator")


cat = read_events_from_csv("catalog.csv")
event = cat[0]
origin = event.preferred_origin() or event.origins[0]  # event origin
eventid = origin.time.strftime("%Y%m%d%H%M%S")  # event ID based on origin time

model = TauPyModel(model="iasp91")
inv = client.get_stations(
    startime=origin.time,
    endtime=origin.time,
    channel="BHZ", 
    level="channel",
)


bulk = []
for net in inv:
    for sta in net:
       
        # let's assume that all channels are at the same locations.
        gcdist = locations2degrees(origin.latitude, origin.longitude, sta.latitude, sta.longitude)
        phasetime = model.get_travel_times(
            source_depth_in_km=origin.depth / 1000.0,
            distance_in_degree=gcdist,
            phase_list=["ttp"],
        )[0].time
        startime = origin.time + phasetime + 0
        endtime = origin.time + phasetime + 120

        for chn in sta:
            bulk.append((net.code, sta.code, "*", chn.code, startime, endtime))

import pprint

pprint.pprint(bulk)
# st = client.get_waveforms_bulk(bulk)