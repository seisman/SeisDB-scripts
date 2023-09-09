from multiprocessing.dummy import Pool as ThreadPool

import decorator
import io
import sys
import traceback
import warnings
from urllib.parse import urlparse

import obspy

from ...base import HTTPClient
from .. import client
from ..client import raise_on_error
from ..header import FDSNException, URL_MAPPINGS, FDSNNoDataException


def _try_download_bulk(r):
    try:
        return _download_bulk(r)
    except Exception:
        reason = "".join(traceback.format_exception(*sys.exc_info()))
        warnings.warn(
            "Failed to download data of type '%s' from '%s' due to: \n%s" % (
                r["data_type"], r["endpoint"], reason))
        return None


def _download_bulk(r):
    # Figure out the passed credentials, if any. Two possibilities:
    # (1) User and password, given explicitly for the base URLs (or an
    #     explicity given `eida_token` key per URL).
    # (2) A global EIDA_TOKEN key. It will be used for all services that
    #     don't have explicit credentials and also support the `/auth` route.
    credentials = r["credentials"].get(urlparse(r["endpoint"]).netloc, {})
    try:
        c = client.Client(r["endpoint"], debug=r["debug"],
                          timeout=r["timeout"], **credentials)
    # This should rarely happen but better safe than sorry.
    except FDSNException as e:  # pragma: no cover
        msg = e.args[0]
        msg += "It will not be used for routing. Try again later?"
        warnings.warn(msg)
        return None

    if not credentials and "EIDA_TOKEN" in r["credentials"] and \
            c._has_eida_auth:
        c.set_eida_token(r["credentials"]["EIDA_TOKEN"])

    if r["data_type"] == "waveform":
        fct = c.get_waveforms_bulk
        service = c.services["dataselect"]
    elif r["data_type"] == "station":
        fct = c.get_stations_bulk
        service = c.services["station"]

    # Keep only kwargs that are supported by this particular service.
    kwargs = {k: v for k, v in r["kwargs"].items() if k in service}
    bulk_str = ""
    for key, value in kwargs.items():
        bulk_str += "%s=%s\n" % (key, str(value))
    try:
        return fct(bulk_str + r["bulk_str"])
    except FDSNException:
        return None


def _strip_protocol(url):
    url = urlparse(url)
    return url.netloc + url.path


# Does not inherit from the FDSN client as that would be fairly hacky as
# some methods just make no sense for the routing client to have (e.g.
# get_events() but also others).
class BaseRoutingClient(HTTPClient):
    def _filter_requests(self, split):
        """
        Filter requests based on including and excluding providers.

        :type split: dict
        :param split: A dictionary containing the desired routing.
        """
        key_map = {_strip_protocol(url): url for url in split.keys()}

        # Apply both filters.
        f_keys = set(key_map.keys())
        if self.include_providers:
            f_keys = f_keys.intersection(set(self.include_providers))
        f_keys = f_keys.difference(set(self.exclude_providers))

        return {key_map[k]: split[key_map[k]] for k in f_keys}

    def _download_waveforms(self, split, **kwargs):
        return self._download_parallel(split, data_type="waveform", **kwargs)

    def _download_stations(self, split, **kwargs):
        return self._download_parallel(split, data_type="station", **kwargs)

    def _download_parallel(self, split, data_type, **kwargs):
        # Apply the provider filter.
        split = self._filter_requests(split)

        if not split:
            raise FDSNNoDataException(
                "Nothing remains to download after the provider "
                "inclusion/exclusion filters have been applied.")

        if data_type not in ["waveform", "station"]:  # pragma: no cover
            raise ValueError("Invalid data type.")

        # One thread per data center.
        dl_requests = []
        for k, v in split.items():
            dl_requests.append({
                "debug": self._debug,
                "timeout": self._timeout,
                "endpoint": k,
                "bulk_str": v,
                "data_type": data_type,
                "kwargs": kwargs,
                "credentials": self.credentials})
        pool = ThreadPool(processes=len(dl_requests))
        results = pool.map(_try_download_bulk, dl_requests)

        # Merge all results into a single object.
        if data_type == "waveform":
            collection = obspy.Stream()
        elif data_type == "station":
            collection = obspy.Inventory(
                networks=[],
                source="ObsPy FDSN Routing %s" % obspy.__version__)
        else:  # pragma: no cover
            raise ValueError

        for _i in results:
            if not _i:
                continue
            collection += _i

        # Explitly close the thread pool as somehow this does not work
        # automatically under linux. See #2342.
        pool.close()

        return collection

    def _handle_requests_http_error(self, r):
        """
        This assumes the same error code semantics as the base fdsnws web
        services.

        Please overwrite this method in a child class if necessary.
        """
        reason = r.reason.encode()
        if hasattr(r, "content"):
            reason += b" -- " + r.content
        with io.BytesIO(reason) as buf:
            raise_on_error(r.status_code, buf)

    def get_waveforms(self, starttime, endtime, **kwargs):
        bulk = []
        for _i in ["network", "station", "location", "channel"]:
            if _i in kwargs:
                bulk.append(kwargs[_i])
                del kwargs[_i]
            else:
                bulk.append("*")
        bulk.extend([starttime, endtime])
        return self.get_waveforms_bulk([bulk], **kwargs)

    def get_stations(self, **kwargs):
        # Just pass these to the bulk request.
        bulk = [kwargs.pop(key, '*') for key in (
                "network", "station", "location", "channel", "starttime",
                "endtime")]
        return self.get_stations_bulk([bulk], **kwargs)