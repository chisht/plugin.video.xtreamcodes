# -*- coding: utf-8 -*-
"""Full refresh: catalog and XMLTV guide."""
import os

import xbmcgui

from . import common, epg
from .catalog import build_catalog
from .xtream import XtreamClient, XtreamError


def _sub(progress, lo, hi):
    if not progress:
        return None
    return lambda pct, msg: progress(int(lo + (hi - lo) * max(0, min(pct, 100)) / 100.0), msg)


def request_background(mode='full'):
    xbmcgui.Window(10000).setProperty(common.PROP_REQUEST, mode)


def is_syncing():
    return bool(xbmcgui.Window(10000).getProperty(common.PROP_SYNCING))


def run_sync(mode='full', progress=None, abort=None):
    client = XtreamClient.from_settings()
    if not client.configured():
        raise XtreamError('Account is not configured')
    result = {}
    do_epg = mode in ('full', 'epg') and common.setting_bool('epg_enable')

    if mode in ('full', 'catalog'):
        hi = 40 if do_epg else 95
        result.update(build_catalog(client, common.catalog_path(), _sub(progress, 0, hi), abort))

    xml_path = None
    if do_epg:
        offset = common.setting_int('epg_offset', 0)
        past = common.setting_int('epg_past_days', 7)
        # Read the guide straight from the server into the database: saving the
        # XML first wrote hundreds of MB to storage on every update. (If the server
        # cannot be reached or refuses, that error is reported as before.)
        resp, size = client.open_xmltv()
        try:
            try:
                result['programmes'] = epg.build_db(
                    resp, common.epg_path(), past, _sub(progress, 40, 98), abort,
                    offset_min=offset, total=size)
            finally:
                resp.close()
        except common.Aborted:
            raise
        except (ValueError,) + epg.STREAM_ERRORS as e:
            # Connection dropped or slow server: once more the old way, saving
            # the file first so the download does not wait for the processing.
            common.log('EPG streaming failed (%s); downloading it first instead' % e)
            base = common.profile_file('xmltv.xml')
            xml_path = client.download_xmltv(base, _sub(progress, 40, 70), abort)
            try:
                result['programmes'] = epg.build_db(
                    xml_path, common.epg_path(), past, _sub(progress, 70, 98), abort,
                    offset_min=offset)
            except ValueError as e:
                raise XtreamError(str(e))
        result['epg_offset'] = offset

    if xml_path and os.path.exists(xml_path):
        os.remove(xml_path)   # parsed into epg.db; no need to keep it

    if progress:
        progress(100, 'Done')
    return result

