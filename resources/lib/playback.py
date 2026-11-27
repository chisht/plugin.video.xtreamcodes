# -*- coding: utf-8 -*-
"""Building playable ListItems; starting live/catch-up with an online check."""
import json
import math
import threading
import time
import urllib.error
import urllib.request

import xbmc
import xbmcgui

from . import common
from .catalog import Catalog
from .xtream import XtreamClient, XtreamError, b64_text


def client():
    return XtreamClient.from_settings()


def has_isa():
    return xbmc.getCondVisibility('System.HasAddon(inputstream.adaptive)')


def has_ffmpegdirect():
    return xbmc.getCondVisibility('System.HasAddon(inputstream.ffmpegdirect)')


def play_item(url, kind='file', info=None, label='', live=False):
    """Build a playable ListItem. kind: 'ts' | 'hls' | 'file'. Returns (path, li)."""
    headers = common.kodi_header_string()
    if kind == 'hls' and common.setting_bool('use_isa') and has_isa():
        path = url
        li = xbmcgui.ListItem(label, path=path, offscreen=True)
        li.setProperty('inputstream', 'inputstream.adaptive')
        li.setProperty('inputstream.adaptive.manifest_headers', headers)
        li.setProperty('inputstream.adaptive.stream_headers', headers)
        li.setMimeType('application/vnd.apple.mpegurl')
    else:
        path = url + '|' + headers
        li = xbmcgui.ListItem(label, path=path, offscreen=True)
        if kind == 'ts':
            li.setMimeType('video/mp2t')
            if live and common.setting_int('live_engine') == 1 and has_ffmpegdirect():
                li.setProperty('inputstream', 'inputstream.ffmpegdirect')
                li.setProperty('inputstreamaddon', 'inputstream.ffmpegdirect')
                li.setProperty('inputstream.ffmpegdirect.is_realtime_stream', 'true')
                li.setProperty('inputstream.ffmpegdirect.stream_mode', 'timeshift')
                li.setProperty('inputstream.ffmpegdirect.manifest_type', 'ts')
                li.setProperty('inputstream.ffmpegdirect.open_mode', 'ffmpeg')
        elif kind == 'hls':
            li.setMimeType('application/vnd.apple.mpegurl')
    li.setContentLookup(False)   # avoid HEAD probes some panels reject
    if info:
        common.set_video_info(li, info)
    return path, li


def live_item(row):
    """(path, ListItem) for a catalog channel row."""
    hls = common.setting_int('live_format') == 1
    url = client().live_url(row['stream_id'], 'm3u8' if hls else 'ts')
    path, li = play_item(url, 'hls' if hls else 'ts',
                         {'title': row['name'], 'mediatype': 'video'}, label=row['name'], live=True)
    if row['icon']:
        li.setArt({'thumb': row['icon'], 'icon': row['icon']})
    return path, li


HISTORY_FILE = 'channel_history.json'
HISTORY_KEEP = 10   # per kind: adult and non-adult are capped separately


def _row_adult(row):
    try:
        return bool(row['adult'])
    except (KeyError, IndexError, TypeError):
        return False


def zap_state():
    raw = xbmcgui.Window(10000).getProperty(common.PROP_ZAP)
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


def remember_zap(cat_id, stream_id, cursor=None, row=None, mode=None, windowed=False):
    """Remember the playing channel.

    cursor: where Up/Down continues from, if different.
    mode:   'restart' while a programme is replayed from its beginning.
    Also keeps the previously watched channel for channel recall.
    """
    old = zap_state() or {}
    data = {'cat': cat_id or '*', 'id': str(stream_id), 't': time.time()}
    if windowed:
        data['w'] = 1
    if cursor:
        data['cursor'] = str(cursor)
        data['t'] = old.get('t', 0)
    if mode:
        data['mode'] = mode
    if old.get('id') and old['id'] != data['id']:
        data['prev'], data['prev_cat'] = old['id'], old.get('cat') or '*'
    elif old.get('prev'):
        data['prev'], data['prev_cat'] = old['prev'], old.get('prev_cat') or '*'
    xbmcgui.Window(10000).setProperty(common.PROP_ZAP, json.dumps(data))
    if cursor:
        return   # nothing new is playing
    # Recently watched channels, newest first, with an adult flag so TV mode
    # never reopens on an adult channel.
    entry = {'cat': data['cat'], 'id': data['id'], 'adult': _row_adult(row)}
    items = [entry] + [e for e in common.load_json(HISTORY_FILE, []) if e.get('id') != entry['id']]
    # Cap adult and normal channels separately, so watching any number of adult
    # channels never pushes the last normal ones out of the history.
    normal = [e for e in items if not e.get('adult')][:HISTORY_KEEP]
    adult = [e for e in items if e.get('adult')][:HISTORY_KEEP]
    keep = {id(e) for e in normal + adult}
    common.save_json(HISTORY_FILE, [e for e in items if id(e) in keep])


def history():
    """Recently watched channels, newest first (includes the pre-1.6 single entry)."""
    items = common.load_json(HISTORY_FILE, [])
    legacy = common.load_json('last_channel.json', None)
    if legacy and not any(e.get('id') == str(legacy.get('id')) for e in items):
        items.append({'cat': legacy.get('cat') or '*', 'id': str(legacy.get('id')), 'adult': None})
    return items


# ------------------------------------------------------- online check
OFFLINE_FOR = 10 * 60   # seconds a failed channel stays marked offline


def _offline_map():
    raw = xbmcgui.Window(10000).getProperty(common.PROP_OFFLINE)
    try:
        data = json.loads(raw) if raw else {}
    except ValueError:
        data = {}
    now = time.time()
    return {k: v for k, v in data.items() if v > now}


_OFFLINE_CACHE = {'t': 0.0, 'ids': frozenset()}


def offline_ids():
    """Channels currently marked offline (cached ~1s: lists call this per item)."""
    now = time.time()
    if now - _OFFLINE_CACHE['t'] > 1.0:
        _OFFLINE_CACHE['ids'] = (frozenset(_offline_map()) if common.setting_bool('mark_offline')
                                 else frozenset())
        _OFFLINE_CACHE['t'] = now
    return _OFFLINE_CACHE['ids']


def is_offline(stream_id):
    return str(stream_id) in offline_ids()


def set_offline(stream_id, offline):
    _OFFLINE_CACHE['t'] = 0.0
    data = _offline_map()
    if offline:
        data[str(stream_id)] = time.time() + OFFLINE_FOR
    else:
        data.pop(str(stream_id), None)
    xbmcgui.Window(10000).setProperty(common.PROP_OFFLINE, json.dumps(data))


def probe(url, timeout):
    """Open the stream and read its first bytes. Returns (ok, reason)."""
    req = urllib.request.Request(url, headers={
        'User-Agent': common.user_agent(), 'Accept': '*/*', 'Connection': 'close'})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        return False, 'HTTP %d' % e.code
    except Exception as e:   # URLError, timeout, reset...
        return False, str(getattr(e, 'reason', e))
    try:
        reader = getattr(resp, 'read1', resp.read)
        data = reader(4096)
    except Exception as e:
        return False, 'no data (%s)' % e
    finally:
        resp.close()
    if not data:
        return False, 'empty response'
    head = data[:64].lstrip()
    if head[:1] in (b'<', b'{'):   # HTML/JSON error page instead of video
        return False, 'not a video stream'
    return True, ''


def check(url, stream_id=None, name=''):
    """Online check honouring settings."""
    if not common.setting_bool('check_stream'):
        return True
    timeout = max(1, common.setting_int('check_timeout', 5))
    # No Kodi busy dialog here: 'busydialognocancel' can stay stuck on screen
    # and block the remote (seen when opened while TV mode is starting).
    ok, reason = probe(url, timeout)
    if stream_id is not None:
        set_offline(stream_id, not ok)
    if not ok:
        common.log('Stream check failed for %s: %s' % (name or url.split('?')[0], reason))
    return ok


def live_url_raw(row):
    hls = common.setting_int('live_format') == 1
    return client().live_url(row['stream_id'], 'm3u8' if hls else 'ts')


def check_live(row):
    return check(live_url_raw(row), row['stream_id'], row['name'])


def offline_notice(name):
    common.notify('%s is offline right now' % name, 3000)


def free_connection():
    """Stop our stream before opening another one.

    Plans with a connection limit refuse a new stream (HTTP 403) while the old one
    is still open, and the online check would wrongly report the channel offline.
    """
    if not common.setting_bool('switch_stop_first'):
        common.log('Not closing the current stream first (setting is off)')
        return False
    player = xbmc.Player()
    try:
        if not (player.isPlaying() and player.getPlayingFile().startswith(client().base + '/')):
            return False
    except RuntimeError:
        return False
    common.log('Closing the current stream before opening the next one')
    player.stop()
    monitor = xbmc.Monitor()
    for _ in range(30):              # wait up to 3 s for the player to close
        if not player.isPlaying() or monitor.waitForAbort(0.1):
            break
    monitor.waitForAbort(0.3)        # let the server register the disconnect
    return True


def own_group(row):
    """The group a channel belongs to: where Up/Down continue when it was reached
    without browsing a group (search, reminders, a number typed in fullscreen)."""
    try:
        return str(row['category_id']) if row['category_id'] not in (None, '') else '*'
    except (KeyError, IndexError, TypeError):
        return '*'


# ---------------------------------------------- "Starting..." feedback
UI = {'win': None}   # the add-on window on screen (TV mode / grid guide), if any


def announce_start(name):
    """Say right away that a channel is being opened (it takes a second or two).

    Inside TV mode or the grid guide the note replaces the mini player until the
    picture appears; anywhere else (lists, search, reminders) it is a short pop-up.
    """
    win = UI['win']
    if win is None:
        common.notify('Starting %s...' % name, 3000)
        return
    win.setProperty('tuning', 'Starting\n%s...' % name)
    until = time.time() + 2.5

    def clear():
        monitor = xbmc.Monitor()
        while time.time() < until:
            if monitor.waitForAbort(0.2):
                return
        for _ in range(60):   # keep it while Kodi is still buffering
            if not xbmc.getCondVisibility('Player.Caching') or monitor.waitForAbort(0.2):
                break
        if UI['win'] is win:
            try:
                win.setProperty('tuning', '')
            except Exception:
                pass
    threading.Thread(target=clear, daemon=True).start()


def announce_end():
    win = UI['win']
    if win is not None:
        try:
            win.setProperty('tuning', '')
        except Exception:
            pass


def start_live(row, cat_id, windowed=False, announce=True):
    """Check and play a channel. Returns False (with a notice) if it is offline."""
    t_start = time.time()
    if announce:
        announce_start(row['name'])
    free_connection()
    if not check_live(row):
        announce_end()
        offline_notice(row['name'])
        return False
    path, li = live_item(row)
    remember_zap(cat_id, row['stream_id'], row=row, windowed=windowed)
    common.log('Opening %s: ready to play after %.1fs' % (row['name'], time.time() - t_start))
    xbmcgui.Window(10000).clearProperty(common.ADDON_ID + '.trakt_now')
    # timing for the "Picture on screen" log line (was only set by Up/Down)
    xbmcgui.Window(10000).setProperty(PROP_TUNE_T, '%f' % t_start)
    xbmc.Player().play(path, li, windowed)
    return True


def start_catchup(stream_id, start, duration_min, title, windowed=False, restart=False):
    if not restart:
        st = zap_state()
        if st and st.get('mode'):   # plain catch-up: Up/Down keep their normal job
            st.pop('mode')
            xbmcgui.Window(10000).setProperty(common.PROP_ZAP, json.dumps(st))
    cl = client()
    url = cl.catchup_url(stream_id, start, duration_min, common.setting_int('catchup_style'))
    announce_start(title)
    free_connection()
    if not check(url, name=title):
        announce_end()
        common.notify('This recording is not available', 3000)
        return False
    path, li = play_item(url, 'ts', {'title': title, 'mediatype': 'video'}, label=title)
    xbmcgui.Window(10000).clearProperty(common.ADDON_ID + '.trakt_now')
    xbmc.Player().play(path, li, windowed)
    return True


# ------------------------------------------------- catch-up helpers
def catchup_start(stream_id, start_ts):
    """Server-local start time for a programme (needed by timeshift URLs)."""
    try:
        for e in client().epg_table(stream_id):
            if str(e.get('start_timestamp')) == str(int(start_ts)):
                if e.get('start'):
                    return e['start']
    except XtreamError as e:
        common.log('EPG table failed: %s' % e)
    return time.strftime('%Y-%m-%d:%H-%M', time.localtime(start_ts))


def current_programme(stream_id):
    """The programme airing now, from the server's archive listing."""
    now = time.time()
    for e in client().epg_table(stream_id):
        try:
            start, stop = int(e.get('start_timestamp')), int(e.get('stop_timestamp'))
        except (TypeError, ValueError):
            continue
        if start <= now < stop:
            return {'start': start, 'stop': stop, 'start_str': e.get('start') or '',
                    'title': b64_text(e.get('title'))}
    return None


def play_programme(row, p, windowed=False):
    """Catch-up for a past programme dict {start, stop, title}."""
    start = catchup_start(row['stream_id'], p['start'])
    dur = int(math.ceil((p['stop'] - p['start']) / 60.0)) + common.setting_int('catchup_pad', 5)
    return start_catchup(row['stream_id'], start, dur, p.get('title') or row['name'], windowed)


def restart(row, cat_id, windowed=False, confirm=False):
    """Watch the programme airing now from its beginning (catch-up channels)."""
    if not row['archive']:
        common.notify('Restart is not available on this channel', 3000)
        return False
    try:
        p = current_programme(row['stream_id'])
    except XtreamError as e:
        common.notify(str(e), 4000)
        return False
    if not p:
        common.notify('No programme information to restart', 3000)
        return False
    title = p['title'] or row['name']
    if confirm and not xbmcgui.Dialog().yesno(row['name'], 'Watch "%s" from the beginning?' % title):
        return False
    start = p['start_str'] or time.strftime('%Y-%m-%d:%H-%M', time.localtime(p['start']))
    dur = int(math.ceil((p['stop'] - p['start']) / 60.0)) + common.setting_int('catchup_pad', 5)
    if not start_catchup(row['stream_id'], start, dur, title, windowed, restart=True):
        return False
    remember_zap(cat_id, row['stream_id'], row=row, mode='restart')
    return True


def recall(windowed=False):
    """Switch back to the previously watched channel."""
    st = zap_state() or {}
    if not st.get('prev'):
        common.notify('No previous channel yet', 2500)
        return None
    cat = Catalog(common.catalog_path())
    row = cat.get('live', st['prev'])
    cat.close()
    if row is None:
        common.notify('Previous channel is not available', 2500)
        return None
    return row if start_live(row, st.get('prev_cat') or '*', windowed, announce=False) else None


def playing_context(base=None):
    """Zap state if one of our live channels (or a restarted programme) is playing."""
    player = xbmc.Player()
    if not player.isPlayingVideo():
        return None
    try:
        playing = player.getPlayingFile()
    except RuntimeError:
        return None
    st = zap_state()
    if not st:
        return None
    base = base or client().base
    if playing.startswith(base + '/live/'):
        return st
    if st.get('mode') == 'restart' and (playing.startswith(base + '/timeshift/')
                                        or '/streaming/timeshift.php' in playing):
        return st
    return None


TUNE_GRACE = 15   # seconds after tuning during which a still-opening channel counts


def zap_context():
    """playing_context(), but also while a channel we just tuned is still opening.

    For a second or two after play() Kodi reports no video playing, so a remote key
    pressed right then fell back to Kodi's own action and the press was lost. The
    keymap only runs in fullscreen video, so if nothing else is playing and we tuned
    a channel moments ago, the key is meant for us.
    """
    st = playing_context()
    if st:
        return st
    st = zap_state()
    if not st:
        return None
    player = xbmc.Player()
    if player.isPlayingVideo():
        return None           # video is up and it is not one of our live channels
    try:
        playing = player.getPlayingFile() if player.isPlaying() else ''
    except RuntimeError:
        playing = ''
    if playing and not playing.startswith(client().base + '/live/'):
        return None           # something else is opening (a movie, catch-up, ...)
    try:
        t0 = float(xbmcgui.Window(10000).getProperty(PROP_TUNE_T) or 0)
    except ValueError:
        t0 = 0.0
    if time.time() - max(t0, float(st.get('t') or 0)) > TUNE_GRACE:
        return None
    return st


# ----------------------------------------------- failed channel starts
PROP_TUNE_T = common.ADDON_ID + '.tune_t'
PROP_LIVE_OK = common.ADDON_ID + '.live_ok'      # id of the channel that started fine
PROP_RETRIED = common.ADDON_ID + '.live_retried'  # id already retried once
PROP_HANDLED = common.ADDON_ID + '.live_handled'   # failure already dealt with
FRESH = 25   # seconds: a failure this soon after tuning counts as a failed start


class LiveRecovery(xbmc.Player):
    """Lives in the service. When a channel fails to start (provider hiccup), try it
    once more; if it fails again, go back to the channel watched before, instead of
    leaving the viewer on Kodi's error message."""

    _acted = 0.0   # when this class last started a channel itself

    def onAVStarted(self):
        st = playing_context()
        if st:
            t0 = xbmcgui.Window(10000).getProperty(PROP_TUNE_T)
            try:
                common.log('Picture on screen %.1fs after the channel change' % (time.time() - float(t0)))
            except ValueError:
                pass
            # Remember which channel started, and when: a late callback from the
            # channel before can arrive just after the next one was tuned.
            xbmcgui.Window(10000).setProperty(PROP_LIVE_OK, '%s|%f' % (st['id'], time.time()))

    def onPlayBackError(self):
        self._failed(error=True)

    def onPlayBackEnded(self):
        self._failed()

    def _started(self, st):
        """True if the channel in zap state `st` had really started playing."""
        raw = xbmcgui.Window(10000).getProperty(PROP_LIVE_OK)
        sid, _, when = raw.partition('|')
        try:
            when = float(when)
        except ValueError:
            when = 0.0
        # Nothing can be on screen within a second of tuning, so a start reported
        # that early belongs to the previous channel.
        return sid == st['id'] and when >= st.get('t', 0) + 1.0

    def _failed(self, error=False):
        if not common.setting_bool('zap_recover'):
            return
        win = xbmcgui.Window(10000)
        st = zap_state()
        if not st or st.get('mode'):
            return
        if time.time() - self._acted < 1.5:
            return             # second report of the failure just handled (error + ended)
        age = time.time() - st.get('t', 0)
        if age > FRESH:
            common.log('Playback ended %.0fs after tuning: not treated as a failed start' % age)
            return
        if not error and self._started(st):
            common.log('Playback ended after the channel had started: left alone')
            return
        key = '%s|%s' % (st['id'], st.get('t'))
        if win.getProperty(PROP_HANDLED) == key:
            return             # Kodi can report one failure twice (error + ended)
        win.setProperty(PROP_HANDLED, key)
        cat = Catalog(common.catalog_path())
        row = cat.get('live', st['id'])
        prev = cat.get('live', st['prev']) if st.get('prev') else None
        cat.close()
        if row is None:
            return
        windowed = bool(st.get('w'))
        monitor = xbmc.Monitor()
        monitor.waitForAbort(0.4)
        xbmc.executebuiltin('Dialog.Close(okdialog,true)')   # Kodi's "playback failed"
        if win.getProperty(PROP_RETRIED) != st['id']:
            win.setProperty(PROP_RETRIED, st['id'])
            common.log('%s failed to start: trying once more' % row['name'])
            monitor.waitForAbort(1.0)
            path, li = live_item(row)
            remember_zap(st.get('cat'), row['stream_id'], row=row, windowed=windowed)
            xbmc.Player().play(path, li, windowed)
            self._acted = time.time()
            return
        win.clearProperty(PROP_RETRIED)
        set_offline(row['stream_id'], True)
        if prev is not None and prev['stream_id'] != row['stream_id']:
            common.log('%s failed twice: back to %s' % (row['name'], prev['name']))
            common.notify('%s is not working right now - back to %s' % (row['name'], prev['name']), 4000)
            path, li = live_item(prev)
            remember_zap(st.get('prev_cat') or '*', prev['stream_id'], row=prev, windowed=windowed)
            xbmc.Player().play(path, li, windowed)
            self._acted = time.time()
        else:
            common.notify('%s is not working right now' % row['name'], 4000)
        monitor.waitForAbort(0.5)
        xbmc.executebuiltin('Dialog.Close(okdialog,true)')
