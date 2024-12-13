"""
Get seismic waveforms from multiple datacenters using the FDSN routing service.

This script is an enhanced version of the ObsPy's RoutingClient. It allows you to
specify the time window based on seismic phase arrival times.
"""
from obspy.clients.fdsn.routing.federator_routing_client import FederatorRoutingClient
from obspy.clients.fdsn.header import FDSNNoDataException
from obspy.taup import TauPyModel

class EnhancedFederatorRoutingClient(FederatorRoutingClient):
    """
    Enhanced FederatorRoutingClient that allows more control over the request.
    """

    def __init__(
        self, debug=False, timeout=120, include_providers=None, exclude_providers=None, **kwargs
    ):
        """
        Initialize the client.

        Parameters
        ----------
        debug : bool, optional
            If True, print out debug information.
        timeout : int, optional
            Timeout in seconds.
        include_providers : list of str, optional
            List of providers to include. If not given, all providers are
            included.
        exclude_providers : list of str, optional
            List of providers to exclude. If not given, no providers are
            excluded.
        """
        super().__init__(
            url="http://service.iris.edu/irisws/fedcatalog/1",
            debug=debug,
            timeout=timeout,
            include_providers=include_providers,
            exclude_providers=exclude_providers,
            **kwargs,
        )

    def get_available_channels(self, **kwargs):
        """
        Get available channels from the federator.

        Accepted parameters are available from http://service.iris.edu/irisws/fedcatalog/1/.
        """
        # parameters that should be passed
        params = {k: str(kwargs[k]) for k in self.kwargs_of_interest if k in kwargs}
        params["format"] = "request"

        # request the available channels
        r = self._download(
            self._url + "/query", params=params, content_type="text/plain"
        )

        # split the responses for multiple datacenters
        split = self._split_routing_response(
            r.content.decode() if hasattr(r.content, "decode") else r.content,
            service="station",
        )
        # filter requests based on including and excluding providers
        split = self._filter_requests(split)

        if not split:
            raise FDSNNoDataException(
                "Nothing remains to download after the provider "
                "inclusion/exclusion filters have been applied."
            )
        return split
# %%

class Record:
    def __init__(self, net, sta, loc, cha, starttime, endtime):
        self.net = net
        self.sta = sta
        self.loc = loc
        self.cha = cha
        self.starttime = starttime
        self.endtime = endtime
        self.latitude = None
        self.longitude = None

    def __str__(self) -> str:
        return f"{self.net} {self.sta} {self.loc} {self.cha} {self.starttime} {self.endtime}"

# %%
def update_request(split, inv):
    # convert the records to a dict of lists of Record objects
    for k, v in split.items():
        split[k] = [Record(*rec.split()) for rec in v.splitlines()]

    # maintain a dict of latitudes and longitudes
    latitudes, longitudes = {}, {}
    for net in inv:
        for sta in net:
            key = f"{net.code}.{sta.code}"
            latitudes[key] = sta.latitude
            longitudes[key] = sta.longitude

    # assign the latitudes and longitudes to the records
    for k, v in split.items():
        for rec in v:
            key = f"{rec.net}.{rec.sta}"
            if key not in latitudes.keys():
                continue
            rec.latitude = latitudes[key]
            rec.longitude = longitudes[key]



    # convert the records back to a dict of strings
    for k, v in split.items():
        split[k] = "\n".join([str(rec) for rec in v])

    return split


client = EnhancedFederatorRoutingClient(timeout=30)

records = client.get_available_channels(
    channel="BHZ",
    starttime="1995-11-14T06:32:55.750000Z",
    endtime="1995-11-14T06:35:55.750000Z",
)

inv = client._download_stations(records, level="response")
model = TauPyModel(model="iasp91")

ttimes = {}
for net in inv:
    for sta in net:
        key = f"{net.code}.{sta.code}"
        arrivals = model.get_travel_times(
            source_depth_in_km=10,
            distance_in_degree=0,
            phase_list=["P", "S"],
            receiver_depth_in_km=0,
        )
        for arr in arrivals:
            if arr.name == "P":
                sta.starttime = sta.starttime + arr.time - 10
                sta.endtime = sta.starttime + arr.time + 30

            #if arr.name == "S":
            #    sta.endtime = sta.starttime + arr.time

records = update_request(records, inv)
st = client._download_waveforms(records)
print(inv)
print(len(st))
# %%
