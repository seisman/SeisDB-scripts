"""
Download seismic wavefrom data from multiple data centers via FDSN web service.
"""
from obspy.clients.fdsn import RoutingClient
from obspy.geodetics import locations2degrees
from obspy.taup import TauPyModel

from helpers import read_events_from_csv

client = RoutingClient("iris-federator", debug=True)
model = TauPyModel(model="iasp91")

cat = read_events_from_csv("catalog.csv")
for event in cat[0:1]:
    origin = event.preferred_origin() or event.origins[0]  # event origin
    eventid = origin.time.strftime("%Y%m%d%H%M%S")  # event ID based on origin time

    print(origin.time)
    inv = client.get_stations(
        starttime=origin.time,
        endtime=origin.time + 100,
        channel="BHZ",
        level="station",
    )
    print(inv)


# bulk = []
# for net in inv:
#     for sta in net:
#         # let's assume that all channels are at the same locations.
#         gcdist = locations2degrees(
#             origin.latitude, origin.longitude, sta.latitude, sta.longitude
#         )
#         phasetime = model.get_travel_times(
#             source_depth_in_km=origin.depth / 1000.0,
#             distance_in_degree=gcdist,
#             phase_list=["ttp"],
#         )[0].time
#         startime = origin.time + phasetime + 0
#         endtime = origin.time + phasetime + 120

#         for chn in sta:
#             bulk.append((net.code, sta.code, "*", chn.code, startime, endtime))

# import pprint

# pprint.pprint(bulk)
# # st = client.get_waveforms_bulk(bulk)
