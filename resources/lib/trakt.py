# -*- coding: utf-8 -*-
"""Trakt.tv: device-code linking, watched-history sync, matching and scrobbling.

Trakt requires every app to have its own API key, so the user creates a free
API app at https://trakt.tv/oauth/applications and enters its Client ID and
Client Secret in the add-on settings.
"""
import json
import re
import time
import urllib.error
import urllib.request

import xbmc
import xbmcgui

from . import common

API = 'https://api.trakt.tv'
TOKEN_FILE = 'trakt_token.json'
WATCHED_FILE = 'trakt_watched.json'
PROP_NOW = common.ADDON_ID + '.trakt_now'   # JSON describing the VOD/episode being played
SYNC_EVERY = 30 * 60


class TraktError(Exception):
    pass


# ----------------------------------------------------------------- titles
_PREFIXES = [re.compile(p) for p in (
    r'^\s*\|[^|]{1,8}\|\s*',                 # |EN| Title
    r'^\s*\[[^\]]{1,8}\]\s*',                # [4K] Title
    r'^\s*[A-Z]{2,3}\s*\|\s*',               # UK | Title
    r'^\s*[A-Z0-9]{2,4}\s+-\s+',             # EN - Title / 4K - Title
)]
_YEAR = re.compile(r'[\(\[]((?:19|20)\d\d)[\)\]]')


def clean_title(name):
    """Provider name -> (title, year): strips tags like 'EN - ' and '(2008)'."""
    s = name or ''
    for _ in range(3):
        for p in _PREFIXES:
            s = p.sub('', s, count=1)
    year = None
    m = _YEAR.search(s)
    if m:
        year = m.group(1)
        s = (s[:m.start()] + s[m.end():])
    return s.strip(' -|:'), year


def title_key(name):
    title, year = clean_title(name)
    return re.sub(r'[^a-z0-9]', '', title.lower()), year


def _tmdb(value):
    v = str(value or '').strip()
    return v if v.isdigit() and v != '0' else ''


# ------------------------------------------------------------ account/http
def creds():
    return common.setting('trakt_client_id').strip(), common.setting('trakt_client_secret').strip()


def configured():
    cid, secret = creds()
    return bool(cid and secret)


def token():
    return common.load_json(TOKEN_FILE, None) or {}


def linked():
    return configured() and bool(token().get('access_token'))


def _http(method, path, body=None, access=None, timeout=20):
    cid, _ = creds()
    headers = {'Content-Type': 'application/json', 'trakt-api-version': '2',
               'trakt-api-key': cid, 'User-Agent': '%s/Kodi' % common.ADDON_ID}
    if access:
        headers['Authorization'] = 'Bearer ' + access
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            code = resp.status
    except urllib.error.HTTPError as e:
        raw, code = e.read(), e.code
    except (urllib.error.URLError, OSError) as e:
        raise TraktError('Cannot reach Trakt: %s' % (getattr(e, 'reason', e),))
    try:
        return code, (json.loads(raw.decode('utf-8')) if raw else None)
    except ValueError:
        return code, None


def _save_token(data):
    tok = token()
    tok.update(data)
    tok.setdefault('created_at', int(time.time()))
    common.save_json(TOKEN_FILE, tok)


def _refresh():
    cid, secret = creds()
    code, data = _http('POST', '/oauth/token', {
        'refresh_token': token().get('refresh_token'), 'client_id': cid,
        'client_secret': secret, 'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
        'grant_type': 'refresh_token'})
    if code == 200 and data and data.get('access_token'):
        data['created_at'] = data.get('created_at') or int(time.time())
        _save_token(data)
        return
    if code in (400, 401):
        common.save_json(TOKEN_FILE, {})
        raise TraktError('Trakt link expired - link your account again in the settings')
    raise TraktError('Trakt token refresh failed (HTTP %s)' % code)


def api(method, path, body=None):
    tok = token()
    if not tok.get('access_token'):
        raise TraktError('Trakt account not linked')
    if time.time() > tok.get('created_at', 0) + tok.get('expires_in', 0) - 3600:
        _refresh()
    code, data = _http(method, path, body, token()['access_token'])
    if code == 401:
        _refresh()
        code, data = _http(method, path, body, token()['access_token'])
    if code == 429:
        raise TraktError('Trakt is rate limiting - try again shortly')
    if code >= 400:
        raise TraktError('Trakt error (HTTP %d)' % code)
    return data


# ---------------------------------------------------------------- linking
def link():
    dialog = xbmcgui.Dialog()
    if not configured():
        dialog.ok('Trakt', 'First create a free API app at [B]trakt.tv/oauth/applications[/B] '
                  '(Redirect URI: urn:ietf:wg:oauth:2.0:oob), then enter its Client ID and '
                  'Client Secret in Settings > Trakt.')
        return False
    cid, secret = creds()
    code, d = _http('POST', '/oauth/device/code', {'client_id': cid})
    if code != 200 or not d:
        dialog.ok('Trakt', 'Trakt did not accept the Client ID (HTTP %s). Check Settings > Trakt.'
                  % code)
        return False
    expires = int(d.get('expires_in', 600))
    interval = int(d.get('interval', 5))
    end = time.time() + expires
    dlg = xbmcgui.DialogProgress()
    dlg.create('Link Trakt account', 'On your phone or computer go to [B]%s[/B][CR]'
               'and enter this code:  [B]%s[/B]' % (d.get('verification_url'), d.get('user_code')))
    monitor = xbmc.Monitor()
    result = None
    try:
        while time.time() < end:
            dlg.update(int((end - time.time()) * 100 / expires))
            if dlg.iscanceled() or monitor.waitForAbort(interval):
                return False
            code, t = _http('POST', '/oauth/device/token', {
                'code': d['device_code'], 'client_id': cid, 'client_secret': secret})
            if code == 200 and t:
                t['created_at'] = t.get('created_at') or int(time.time())
                common.save_json(TOKEN_FILE, t)
                result = True
                break
            if code == 429:
                interval += 1
            elif code in (404, 409, 410, 418):
                result = {404: 'Invalid code.', 409: 'Code already used.',
                          410: 'Code expired.', 418: 'Access was denied on Trakt.'}[code]
                break
    finally:
        dlg.close()
    if result is not True:
        dialog.ok('Trakt', result or 'The code expired. Try again.')
        return False
    try:
        user = (api('GET', '/users/settings') or {}).get('user', {}).get('username', '')
        _save_token({'username': user})
    except TraktError:
        user = ''
    common.notify('Trakt linked%s' % (' as ' + user if user else ''))
    return True


def unlink():
    cid, secret = creds()
    tok = token()
    if tok.get('access_token'):
        try:
            _http('POST', '/oauth/revoke', {'token': tok['access_token'], 'client_id': cid,
                                            'client_secret': secret}, tok['access_token'])
        except TraktError:
            pass
    common.save_json(TOKEN_FILE, {})
    common.save_json(WATCHED_FILE, {})
    common.notify('Trakt unlinked')


# ------------------------------------------------------------ watched sync
def sync_watched():
    """Download watched movies/shows into a compact local cache. Returns counts."""
    movies = api('GET', '/sync/watched/movies') or []
    shows = api('GET', '/sync/watched/shows?extended=full') or []
    out_m, out_s = [], []
    for m in movies:
        mv = m.get('movie') or {}
        out_m.append({'tmdb': _tmdb((mv.get('ids') or {}).get('tmdb')),
                      't': mv.get('title') or '', 'y': str(mv.get('year') or '')})
    for s in shows:
        sh = s.get('show') or {}
        eps = ['%d:%d' % (se.get('number', 0), ep.get('number', 0))
               for se in s.get('seasons') or [] if se.get('number', 0) > 0
               for ep in se.get('episodes') or []]
        out_s.append({'tmdb': _tmdb((sh.get('ids') or {}).get('tmdb')),
                      't': sh.get('title') or '', 'y': str(sh.get('year') or ''),
                      'aired': int(sh.get('aired_episodes') or 0),
                      'last': s.get('last_watched_at') or '', 'eps': eps})
    common.save_json(WATCHED_FILE, {'fetched': int(time.time()), 'movies': out_m, 'shows': out_s})
    return len(out_m), len(out_s)


def mark_local(item):
    """Record a finished scrobble in the cache right away (Trakt syncs later)."""
    data = common.load_json(WATCHED_FILE, {}) or {}
    if not data:
        return
    if item.get('type') == 'movie':
        data.setdefault('movies', []).append(
            {'tmdb': _tmdb(item.get('tmdb')), 't': item.get('title', ''), 'y': str(item.get('year') or '')})
    else:
        key = '%s:%s' % (item.get('season'), item.get('episode'))
        tmdb = _tmdb(item.get('tmdb'))
        tkey = title_key(item.get('title', ''))[0]
        for s in data.setdefault('shows', []):
            if (tmdb and s.get('tmdb') == tmdb) or (not tmdb and title_key(s.get('t'))[0] == tkey):
                if key not in s['eps']:
                    s['eps'].append(key)
                s['last'] = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
                break
        else:
            data['shows'].append({'tmdb': tmdb, 't': item.get('title', ''),
                                  'y': str(item.get('year') or ''), 'aired': 0,
                                  'last': time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime()),
                                  'eps': [key]})
    common.save_json(WATCHED_FILE, data)


class Watched(object):
    """Lookup of Trakt watched state for provider items (by TMDb id, then title)."""

    def __init__(self):
        data = common.load_json(WATCHED_FILE, {}) if linked() else {}
        data = data or {}
        self.ok = bool(data)
        self.m_tmdb, self.m_key, self.m_title = set(), set(), {}
        for m in data.get('movies', []):
            if m.get('tmdb'):
                self.m_tmdb.add(m['tmdb'])
            k = title_key(m.get('t'))[0]
            self.m_key.add('%s|%s' % (k, m.get('y')))
            self.m_title[k] = self.m_title.get(k, 0) + 1
        self.shows = data.get('shows', [])
        self.s_tmdb, self.s_key, self.s_title = {}, {}, {}
        for s in self.shows:
            s['_eps'] = set(s.get('eps') or [])
            if s.get('tmdb'):
                self.s_tmdb[s['tmdb']] = s
            k = title_key(s.get('t'))[0]
            self.s_key['%s|%s' % (k, s.get('y'))] = s
            self.s_title.setdefault(k, []).append(s)

    def movie(self, tmdb, name, year=None):
        if not self.ok:
            return False
        tmdb = _tmdb(tmdb)
        if tmdb and tmdb in self.m_tmdb:
            return True
        key, y = title_key(name)
        y = str(year or y or '')
        if y:
            return '%s|%s' % (key, y) in self.m_key
        return self.m_title.get(key) == 1

    def show(self, tmdb, name, year=None):
        """The Trakt entry for a provider series, or None."""
        if not self.ok:
            return None
        tmdb = _tmdb(tmdb)
        if tmdb and tmdb in self.s_tmdb:
            return self.s_tmdb[tmdb]
        key, y = title_key(name)
        y = str(year or y or '')
        if y and '%s|%s' % (key, y) in self.s_key:
            return self.s_key['%s|%s' % (key, y)]
        same = self.s_title.get(key) or []
        return same[0] if len(same) == 1 else None

    def episodes(self, tmdb, name, year=None):
        s = self.show(tmdb, name, year)
        return s['_eps'] if s else set()


def next_episode(eps):
    """'S02E04' after the highest watched episode, from a set of 'season:episode'."""
    best = max((tuple(int(x) for x in e.split(':')) for e in eps), default=None)
    return 'S%02dE%02d' % (best[0], best[1] + 1) if best else ''


# -------------------------------------------------------------- scrobbling
def _media(item):
    title, year = item.get('title') or '', item.get('year') or None
    tmdb = _tmdb(item.get('tmdb'))
    ref = {'ids': {'tmdb': int(tmdb)}} if tmdb else {'title': title}
    if not tmdb and year and str(year).isdigit():
        ref['year'] = int(year)
    if item.get('type') == 'movie':
        return {'movie': ref}
    return {'show': ref, 'episode': {'season': int(item.get('season') or 0),
                                     'number': int(item.get('episode') or 0)}}


def scrobble(action, item, progress):
    body = _media(item)
    body['progress'] = round(max(0.0, min(float(progress), 100.0)), 2)
    try:
        api('POST', '/scrobble/%s' % action, body)
    except TraktError as e:
        if '409' not in str(e):   # 409 = already scrobbled recently
            common.log('Trakt scrobble %s failed: %s' % (action, e), xbmc.LOGWARNING)


def set_now_playing(item):
    xbmcgui.Window(10000).setProperty(PROP_NOW, json.dumps(item) if item else '')


class Scrobbler(xbmc.Player):
    """Lives in the service: reports VOD/episode playback started from the add-on."""

    def __init__(self):
        super(Scrobbler, self).__init__()
        self.item = None        # what is playing (movie/episode started from the add-on)
        self.trakt = False      # whether it is being reported to Trakt
        self.progress = 0.0
        self.position = 0.0
        self.total = 0.0
        self._saved = 0.0

    def _current(self):
        raw = xbmcgui.Window(10000).getProperty(PROP_NOW)
        try:
            item = json.loads(raw) if raw else None
        except ValueError:
            return None
        if not item:
            return None
        try:
            playing = self.getPlayingFile()
        except RuntimeError:
            return None
        marker = '/%s/' % ('movie' if item.get('type') == 'movie' else 'series')
        return item if marker in playing and '/%s.' % item.get('id') in playing else None

    @staticmethod
    def _enabled():
        return linked() and common.setting_bool('trakt_scrobble')

    def onAVStarted(self):
        self.item = self._current()
        self.progress = self.position = self.total = 0.0
        self._saved = time.time()
        # Library playback is reported by the Trakt add-on itself (it knows those items).
        self.trakt = bool(self.item) and self._enabled() and not self.item.get('lib')
        if self.item:
            self.tick()
            if self.trakt:
                scrobble('start', self.item, self.progress)

    def onPlayBackPaused(self):
        if self.item:
            self.tick()
            self._save_progress()
            if self.trakt:
                scrobble('pause', self.item, self.progress)

    def onPlayBackResumed(self):
        if self.item and self.trakt:
            scrobble('start', self.item, self.progress)

    def _save_progress(self, ended=False):
        from . import watching
        if self.item:
            total = self.total or 1
            watching.update(self.item, total if ended else self.position, total)
            self._saved = time.time()

    def _finish(self, ended=False):
        if not self.item:
            return
        item, progress = self.item, (100.0 if ended else self.progress)
        self._save_progress(ended)
        self.item = None
        set_now_playing(None)
        if self.trakt:
            scrobble('stop', item, progress)
            if progress >= 80:
                mark_local(item)

    def onPlayBackStopped(self):
        self._finish()

    def onPlayBackEnded(self):
        self._finish(ended=True)

    def onPlayBackError(self):
        self.item = None

    def tick(self):
        """Called from the service loop: remember how far playback got."""
        if not self.item:
            return
        try:
            total = self.getTotalTime()
            if total > 0:
                self.position, self.total = self.getTime(), total
                self.progress = self.position * 100.0 / total
        except RuntimeError:
            return
        if time.time() - self._saved > 30:   # survive a crash or power cut
            self._save_progress()
