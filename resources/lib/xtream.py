# -*- coding: utf-8 -*-
"""Minimal Xtream Codes API client (player_api.php / xmltv.php)."""
import base64
import gzip
import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

from . import common


class XtreamError(Exception):
    pass


def normalize_server(url):
    url = (url or '').strip()
    if not url:
        return ''
    if '://' not in url:
        url = 'http://' + url
    parts = urllib.parse.urlsplit(url)
    path = parts.path
    for suffix in ('/player_api.php', '/get.php', '/xmltv.php', '/panel_api.php'):
        if path.endswith(suffix):
            path = path[:-len(suffix)]
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path.rstrip('/'), '', ''))


def b64_text(value):
    """EPG fields from get_simple_data_table/get_short_epg are base64."""
    if not value:
        return ''
    try:
        return base64.b64decode(value, validate=True).decode('utf-8', 'replace')
    except (ValueError, TypeError):
        return value


def _as_list(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.values())
    return []


class XtreamClient(object):
    def __init__(self, server, username, password, user_agent, timeout=30):
        self.base = normalize_server(server)
        self.username = (username or '').strip()
        self.password = (password or '').strip()
        self.user_agent = user_agent
        self.timeout = timeout

    @classmethod
    def from_settings(cls):
        return cls(common.setting('server'), common.setting('username'),
                   common.setting('password'), common.user_agent(),
                   common.setting_int('timeout', 30) or 30)

    def configured(self):
        return bool(self.base and self.username)

    # ---------------------------------------------------------------- http
    def _open(self, url, timeout=None):
        req = urllib.request.Request(url, headers={
            'User-Agent': self.user_agent,
            'Accept': '*/*',
            'Accept-Encoding': 'gzip',
            'Connection': 'close',
        })
        try:
            return urllib.request.urlopen(req, timeout=timeout or self.timeout)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise XtreamError('Access denied (HTTP %d) - check login or User-Agent' % e.code)
            raise XtreamError('Server returned HTTP %d' % e.code)
        except urllib.error.URLError as e:
            raise XtreamError('Cannot reach server: %s' % (e.reason,))
        except (socket.timeout, OSError) as e:
            raise XtreamError('Connection error: %s' % e)

    def _api(self, **params):
        query = {'username': self.username, 'password': self.password}
        query.update({k: v for k, v in params.items() if v is not None})
        url = self.base + '/player_api.php?' + urllib.parse.urlencode(query)
        resp = self._open(url)
        try:
            data = resp.read()
        except (socket.timeout, OSError) as e:
            raise XtreamError('Connection error: %s' % e)
        finally:
            resp.close()
        if data[:2] == b'\x1f\x8b':
            data = gzip.decompress(data)
        text = data.decode('utf-8', 'replace').strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except ValueError:
            raise XtreamError('Server sent an invalid response')

    # ----------------------------------------------------------------- api
    def account(self):
        data = self._api()
        if not isinstance(data, dict) or 'user_info' not in data:
            raise XtreamError('Login failed - check server URL, username and password')
        ui = data.get('user_info') or {}
        if str(ui.get('auth', '1')) == '0':
            raise XtreamError('Login failed - wrong username or password')
        status = str(ui.get('status', 'Active'))
        if status.lower() not in ('active', ''):
            raise XtreamError('Account status: %s' % status)
        return data

    def live_categories(self):
        return _as_list(self._api(action='get_live_categories'))

    def live_streams(self, category_id=None):
        return _as_list(self._api(action='get_live_streams', category_id=category_id))

    def vod_categories(self):
        return _as_list(self._api(action='get_vod_categories'))

    def vod_streams(self, category_id=None):
        return _as_list(self._api(action='get_vod_streams', category_id=category_id))

    def vod_info(self, vod_id):
        data = self._api(action='get_vod_info', vod_id=vod_id)
        return data if isinstance(data, dict) else {}

    def series_categories(self):
        return _as_list(self._api(action='get_series_categories'))

    def series(self, category_id=None):
        return _as_list(self._api(action='get_series', category_id=category_id))

    def series_info(self, series_id):
        data = self._api(action='get_series_info', series_id=series_id)
        return data if isinstance(data, dict) else {}

    def short_epg(self, stream_id, limit=20):
        data = self._api(action='get_short_epg', stream_id=stream_id, limit=limit)
        return _as_list((data or {}).get('epg_listings')) if isinstance(data, dict) else []

    def epg_table(self, stream_id):
        """All listings for a channel, incl. past ones with has_archive flag."""
        data = self._api(action='get_simple_data_table', stream_id=stream_id)
        return _as_list((data or {}).get('epg_listings')) if isinstance(data, dict) else []

    def open_xmltv(self):
        """(response, size in bytes or 0) for reading the guide straight from the server."""
        url = self.base + '/xmltv.php?' + urllib.parse.urlencode(
            {'username': self.username, 'password': self.password})
        resp = self._open(url, timeout=max(self.timeout, 120))
        return resp, int(resp.headers.get('Content-Length') or 0)

    def download_xmltv(self, dest_base, progress=None, abort=None):
        """Stream xmltv.php to disk. Returns the path written (.xml or .xml.gz)."""
        url = self.base + '/xmltv.php?' + urllib.parse.urlencode(
            {'username': self.username, 'password': self.password})
        resp = self._open(url, timeout=max(self.timeout, 120))
        total = int(resp.headers.get('Content-Length') or 0)
        tmp = dest_base + '.part'
        done = 0
        last = 0
        try:
            with open(tmp, 'wb') as f:
                while True:
                    if abort and abort():
                        raise common.Aborted()
                    chunk = resp.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress and time.time() - last > 1:
                        last = time.time()
                        pct = int(done * 100 / total) if total else 0
                        progress(pct, 'Downloading EPG: %.1f MB' % (done / 1048576.0))
        except (socket.timeout, OSError) as e:
            raise XtreamError('EPG download failed: %s' % e)
        finally:
            resp.close()
        if done == 0:
            raise XtreamError('Server returned an empty EPG')
        with open(tmp, 'rb') as f:
            gz = f.read(2) == b'\x1f\x8b'
        final = dest_base + ('.gz' if gz else '')
        other = dest_base if gz else dest_base + '.gz'
        if os.path.exists(other):
            os.remove(other)
        common.atomic_replace(tmp, final)
        return final

    # ---------------------------------------------------------------- urls
    def _creds_path(self):
        return '%s/%s' % (urllib.parse.quote(self.username, safe=''),
                          urllib.parse.quote(self.password, safe=''))

    def live_url(self, stream_id, ext='ts'):
        return '%s/live/%s/%s.%s' % (self.base, self._creds_path(), stream_id, ext)

    def vod_url(self, stream_id, ext='mp4'):
        return '%s/movie/%s/%s.%s' % (self.base, self._creds_path(), stream_id, ext or 'mp4')

    def episode_url(self, episode_id, ext='mp4'):
        return '%s/series/%s/%s.%s' % (self.base, self._creds_path(), episode_id, ext or 'mp4')

    def catchup_url(self, stream_id, start, duration_min, style=0):
        """start: server-local time, 'YYYY-MM-DD HH:MM[:SS]' or 'YYYY-MM-DD:HH-MM'."""
        start = start.strip()
        if ' ' in start:
            day, hm = start.split(' ', 1)
            start = '%s:%s' % (day, hm[:5].replace(':', '-'))
        duration_min = max(1, int(duration_min))
        if style == 1:
            return '%s/streaming/timeshift.php?%s' % (self.base, urllib.parse.urlencode({
                'username': self.username, 'password': self.password,
                'stream': stream_id, 'start': start, 'duration': duration_min}))
        return '%s/timeshift/%s/%d/%s/%s.ts' % (
            self.base, self._creds_path(), duration_min, start, stream_id)
