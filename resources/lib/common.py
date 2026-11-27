# -*- coding: utf-8 -*-
"""Shared helpers: settings, paths, logging, ListItem info."""
import json
import os
import threading
import time
import urllib.parse
import uuid

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON_ID = 'plugin.video.xtreamcodes'
_ADDON = xbmcaddon.Addon(ADDON_ID)
ADDON_NAME = _ADDON.getAddonInfo('name')
ADDON_PATH = xbmcvfs.translatePath(_ADDON.getAddonInfo('path'))
PROFILE = xbmcvfs.translatePath(_ADDON.getAddonInfo('profile'))
ICON = os.path.join(ADDON_PATH, 'icon.png')
FANART = os.path.join(ADDON_PATH, 'fanart.jpg')

# TiviMate (ar.tvplayer.tv) for Android TV. Change in settings if your
# provider expects a different string.
TIVIMATE_UA = 'TiviMate/5.3.3 (Android 12)'

# Home-window properties used to talk to the background service.
PROP_REQUEST = ADDON_ID + '.sync_request'   # value: 'full' | 'catalog' | 'epg'
PROP_SYNCING = ADDON_ID + '.syncing'
PROP_UI_OPEN = ADDON_ID + '.ui_open'   # TV mode or guide on screen
PROP_OFFLINE = ADDON_ID + '.offline'   # JSON {stream_id: until}
PROP_ZAP = ADDON_ID + '.zap'           # JSON {cat, id} of the playing channel


class Aborted(Exception):
    """Raised when Kodi is shutting down or the user cancelled."""


def addon():
    # A fresh instance so the long-running service sees changed settings.
    return xbmcaddon.Addon(ADDON_ID)


def setting(key):
    return addon().getSetting(key)


def setting_bool(key):
    return setting(key).lower() == 'true'


def setting_int(key, default=0):
    try:
        return int(float(setting(key)))
    except (TypeError, ValueError):
        return default


def user_agent():
    if setting_bool('custom_ua_enable'):
        custom = setting('custom_ua').strip()
        if custom:
            return custom
    return TIVIMATE_UA


def kodi_header_string():
    """Headers in Kodi's 'url|Header=value' syntax."""
    return 'User-Agent=' + urllib.parse.quote(user_agent())


def is_configured():
    return bool(setting('server').strip() and setting('username').strip())


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[%s] %s' % (ADDON_ID, msg), level)


def notify(msg, ms=5000, icon=None):
    xbmcgui.Dialog().notification(ADDON_NAME, msg, icon or ICON, ms)


def ensure_profile():
    os.makedirs(PROFILE, exist_ok=True)


def profile_file(name):
    ensure_profile()
    return os.path.join(PROFILE, name)


def catalog_path():
    return profile_file('catalog.db')


def epg_path():
    return profile_file('epg.db')


def atomic_replace(src, dst, tries=10):
    """os.replace with retries (Windows refuses while a reader has it open)."""
    for i in range(tries):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(0.5)


def load_state():
    try:
        with open(profile_file('state.json'), 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state):
    _write_json(profile_file('state.json'), state)


def load_json(name, default):
    try:
        with open(profile_file(name), 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(name, data):
    _write_json(profile_file(name), data)


def _write_json(path, data):
    """Write via a temporary file unique to this writer: TV mode, the service and
    each remote key press run in separate threads/processes and can save the same
    file at the same moment; a shared temp name made one of them fail."""
    tmp = '%s.%d.%d.%s.tmp' % (path, os.getpid(), threading.get_ident(), uuid.uuid4().hex[:6])
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        atomic_replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


STAR = '[COLOR FFFFC107]\u2605[/COLOR] '   # marks a favourite channel in lists


def star():
    """Favourite marker, in the theme's colour."""
    from . import theme
    return '[COLOR %s]\u2605[/COLOR] ' % theme.fav()


def dim(text, t=None):
    """Text shown greyed out: offline channels, programmes that have aired."""
    from . import theme
    return '[COLOR %s]%s[/COLOR]' % ((t or theme.current()).dim, text)


def load_favs():
    return [str(x) for x in load_json('favourites.json', [])]


def toggle_fav(stream_id):
    """Add or remove a channel. Returns True if it is now a favourite."""
    sid = str(stream_id)
    favs = load_favs()
    if sid in favs:
        favs.remove(sid)
        added = False
    else:
        favs.append(sid)
        added = True
    save_json('favourites.json', favs)
    return added


def load_hidden():
    data = load_json('hidden_groups.json', {})
    return {k: set(str(x) for x in v) for k, v in data.items() if isinstance(v, list)}


def save_hidden(hidden):
    save_json('hidden_groups.json', {k: sorted(v) for k, v in hidden.items()})


PROP_UNLOCKED = ADDON_ID + '.adult_unlocked_until'
UNLOCK_HOURS = 3


def adult_unlocked_until():
    try:
        until = float(xbmcgui.Window(10000).getProperty(PROP_UNLOCKED) or 0)
    except ValueError:
        until = 0.0
    return until if until > time.time() else 0.0


def adult_hidden():
    """Adult content is hidden unless the setting is off or the PIN unlocked it."""
    return setting_bool('hide_adult') and not adult_unlocked_until()


def pin_set():
    return bool(setting('adult_pin').strip())


def unlock_adult():
    if not pin_set():
        xbmcgui.Dialog().ok(ADDON_NAME, 'Set a PIN first in Settings > Parental.')
        return False
    entered = xbmcgui.Dialog().numeric(0, 'Enter the PIN for adult content', '', True)
    if not entered:
        return False
    if entered.strip() != setting('adult_pin').strip():
        notify('Wrong PIN', 2500)
        return False
    until = time.time() + UNLOCK_HOURS * 3600
    xbmcgui.Window(10000).setProperty(PROP_UNLOCKED, str(until))
    notify('Adult content shown until %s' % fmt_time(until), 3000)
    return True


def lock_adult():
    xbmcgui.Window(10000).clearProperty(PROP_UNLOCKED)
    notify('Adult content hidden', 2500)


def fmt_time(ts):
    return time.strftime('%H:%M', time.localtime(ts))


def fmt_day_time(ts):
    lt = time.localtime(ts)
    if time.strftime('%Y%m%d', lt) == time.strftime('%Y%m%d'):
        return time.strftime('%H:%M', lt)
    return time.strftime('%a %d %b %H:%M', lt)


def fmt_when(ts, now=None):
    """'Today 21:00', 'Tomorrow 06:30', 'Yesterday 20:00' or 'Fri 21 Nov 21:00':
    a weekday alone could be last week or next week in guide search results."""
    now = now or time.time()
    lt = time.localtime(ts)
    day = time.strftime('%Y%m%d', lt)
    for offset, word in ((0, 'Today'), (1, 'Tomorrow'), (-1, 'Yesterday')):
        if day == time.strftime('%Y%m%d', time.localtime(now + offset * 86400)):
            return '%s %s' % (word, time.strftime('%H:%M', lt))
    return time.strftime('%a %d %b %H:%M', lt)


def fmt_until(ts, now=None):
    """'in 25 min', 'in 3 h', 'in 2 days' for something starting later."""
    secs = max(0, ts - (now or time.time()))
    if secs < 3600:
        return 'in %d min' % max(1, round(secs / 60.0))
    if secs < 2 * 86400:
        return 'in %d h' % round(secs / 3600.0)
    return 'in %d days' % round(secs / 86400.0)


def _float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def set_video_info(li, info):
    """Fill a ListItem's InfoTagVideo (Kodi 20+ API)."""
    tag = li.getVideoInfoTag()
    if info.get('mediatype'):
        tag.setMediaType(info['mediatype'])
    if info.get('title'):
        tag.setTitle(info['title'])
    if info.get('plot'):
        tag.setPlot(info['plot'])
    if info.get('plotoutline'):
        tag.setPlotOutline(info['plotoutline'])
    if info.get('tvshowtitle'):
        tag.setTvShowTitle(info['tvshowtitle'])
    year = _int(info.get('year'))
    if year:
        tag.setYear(year)
    rating = _float(info.get('rating'))
    if rating > 0:
        votes = _int(info.get('votes'))
        if votes:
            tag.setRating(min(rating, 10.0), votes, 'tmdb', True)
        else:
            tag.setRating(min(rating, 10.0))
    duration = _int(info.get('duration'))
    if duration:
        tag.setDuration(duration)
    if info.get('season') not in (None, ''):
        tag.setSeason(_int(info['season']))
    if info.get('episode') not in (None, ''):
        tag.setEpisode(_int(info['episode']))
    if info.get('resume') and info.get('duration'):
        tag.setResumePoint(float(info['resume']), float(info['duration']))
    if info.get('playcount'):
        tag.setPlaycount(_int(info['playcount']))
    if info.get('premiered'):
        tag.setPremiered(str(info['premiered'])[:10])
    for key, setter in (('genre', tag.setGenres), ('director', tag.setDirectors)):
        val = info.get(key)
        if val:
            if isinstance(val, str):
                val = [v.strip() for v in val.replace('/', ',').split(',') if v.strip()]
            setter(val)
    if info.get('cast'):
        cast = info['cast']
        if isinstance(cast, str):
            cast = [c.strip() for c in cast.split(',') if c.strip()]
        tag.setCast([xbmc.Actor(name) for name in cast[:30]])
