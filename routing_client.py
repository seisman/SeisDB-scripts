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


class BaseRoutingClient(HTTPClient):
    def _download_waveforms(self, split, **kwargs):
        return self._download_parallel(split, data_type="waveform", **kwargs)

    def _download_stations(self, split, **kwargs):
        return self._download_parallel(split, data_type="station", **kwargs)

    def _download_parallel(self, split, data_type, **kwargs):
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