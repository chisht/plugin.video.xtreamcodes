# -*- coding: utf-8 -*-
"""Overlays over fullscreen video: the channel banner and channel-number entry.

Every remote key press runs the add-on in a separate process, so overlays are
coordinated through a sequence number in a Home-window property: a newer key
press makes the older overlay close itself.
"""
import contextlib
import json
import time
import uuid

import xbmc
import xbmcgui

from . import common, theme
from .epg import EPG

PROP_SEQ = common.ADDON_ID + '.overlay_seq'
PROP_TYPED = common.ADDON_ID + '.typed'
BANNER_SECONDS = 4.0
DIGIT_WAIT = 2.0
BAR_WIDTH = 1510


class _Overlay(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.bar = 0.0
        self._theme = theme.current()

    def onInit(self):
        try:
            self.getControl(10).setWidth(max(1, int(BAR_WIDTH * self.bar)))
        except (RuntimeError, TypeError):
            pass

    def onAction(self, action):
        # Let any key close it at once; the key itself is handled by the keymap.
        if action.getId() in (10, 92):
            self.close()


def _new_overlay():
    return _Overlay(theme.BANNER_XML, common.ADDON_PATH, theme.skin_dir(), '1080i')


class _Cover(xbmcgui.WindowXMLDialog):
    """Black full-screen dialog; ignores keys (the banner above it handles them)."""
    def __init__(self, *args, **kwargs):
        pass

    def onAction(self, action):
        pass


COVER_MAX = 15.0


@contextlib.contextmanager
def fullscreen_cover():
    """Hide the window Kodi falls back to while a channel changes from fullscreen.

    Closing the old stream makes Kodi leave fullscreen video (for TV or grid mode,
    where the channel list would show) until the next stream is on screen. When a
    channel is changed from fullscreen, a black cover (below the banner) stays up
    until the picture is back, so the viewer never leaves fullscreen.
    """
    win = None
    try:
        if (common.setting_bool('switch_stop_first')
                and xbmc.getCondVisibility('Window.IsActive(fullscreenvideo)')):
            win = _Cover(theme.COVER_XML, common.ADDON_PATH, theme.skin_dir(), '1080i')
            win.show()
    except Exception:
        win = None
    try:
        yield
    finally:
        if win is not None:
            _drop_cover(win)


def _drop_cover(win):
    monitor = xbmc.Monitor()
    player = xbmc.Player()
    start = time.time()
    try:
        while time.time() - start < COVER_MAX:
            if xbmc.getCondVisibility('Window.IsActive(fullscreenvideo)'):
                break
            if time.time() - start > 3 and not player.isPlaying():
                break               # nothing is opening: do not hide the window for nothing
            if monitor.waitForAbort(0.1):
                break
    except Exception:
        pass
    try:
        win.close()
    except Exception:
        pass


def _claim():
    seq = uuid.uuid4().hex
    xbmcgui.Window(10000).setProperty(PROP_SEQ, seq)
    return seq


def _still_mine(seq):
    return xbmcgui.Window(10000).getProperty(PROP_SEQ) == seq


def _hold(win, seq, seconds):
    """Keep the overlay up until it times out or a newer overlay takes over."""
    monitor = xbmc.Monitor()
    end = time.time() + seconds
    while time.time() < end and _still_mine(seq):
        if monitor.waitForAbort(0.1):
            break
    win.close()


def banner_data(row, extra=''):
    now = time.time()
    data = {'logo': row['icon'] or common.ICON, 'num': str(row['num'] or ''),
            'name': row['name'], 'extra': extra, 'now': '', 'next': '', 'has_now': '', 'bar': 0.0}
    guide = EPG(common.epg_path())
    try:
        progs = guide.now_next([row['epg_id']], count=2).get(row['epg_id']) or []
    finally:
        guide.close()
    for p in progs:
        if p['start'] <= now < p['stop'] and not data['now']:
            data['now'] = '%s - %s   %s' % (common.fmt_time(p['start']), common.fmt_time(p['stop']),
                                            p['title'])
            data['has_now'] = '1'
            data['bar'] = (now - p['start']) / float(max(1, p['stop'] - p['start']))
        elif p['start'] >= now and not data['next']:
            data['next'] = 'Next  %s   %s' % (common.fmt_time(p['start']), p['title'])
    if not progs:
        data['now'] = 'No programme information'
    return data


def show_banner(row, extra='', during=None):
    """Channel banner for a few seconds (blocks this add-on call meanwhile).

    `during` runs once the banner is on screen (before it is held), so the
    banner can appear first and the slower work follow."""
    data = banner_data(row, extra)
    seq = _claim()
    win = _new_overlay()
    win.bar = data.pop('bar')
    for k, v in data.items():
        win.setProperty(k, v)
    win.show()
    if during:
        during()
    _hold(win, seq, BANNER_SECONDS)


# ------------------------------------------------------ number entry
def _typed():
    raw = xbmcgui.Window(10000).getProperty(PROP_TYPED)
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


def digit(d, lookup):
    """Handle one digit key in fullscreen.

    Returns ('recall', None) for a lone 0, ('tune', number) once typing has
    finished, or (None, None) if a newer key press took over.
    """
    win10000 = xbmcgui.Window(10000)
    buf = _typed()
    now = time.time()
    if buf and now - buf.get('t', 0) < DIGIT_WAIT + 0.3:
        digits = (buf['s'] + d)[-5:]
    elif d == '0':
        return 'recall', None
    else:
        digits = d
    seq = _claim()
    win10000.setProperty(PROP_TYPED, json.dumps({'s': digits, 't': now}))
    row = lookup(int(digits))
    win = _new_overlay()
    win.setProperty('digits', digits)
    win.setProperty('digits_name', row['name'] if row is not None else 'No channel %s' % digits)
    win.show()
    monitor = xbmc.Monitor()
    end = time.time() + DIGIT_WAIT
    while time.time() < end and _still_mine(seq):
        if monitor.waitForAbort(0.1):
            break
    win.close()
    if not _still_mine(seq):
        return None, None          # another digit followed; that call carries on
    win10000.clearProperty(PROP_TYPED)
    return 'tune', int(digits)
