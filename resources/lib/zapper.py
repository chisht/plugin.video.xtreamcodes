# -*- coding: utf-8 -*-
"""Remote keys while live TV plays fullscreen (channel up/down, numbers, info,
guide, restart).

Called from the plugin (keymap -> RunPlugin) or, faster, from the background
service (keymap -> NotifyAll), where nothing has to be loaded for each press.
"""
import time
import uuid

import xbmc
import xbmcgui

from . import common, playback
from .catalog import Catalog, live_rows
from .playback import live_item, remember_zap


ZAP_FALLBACK = {'up': 'Action(ChapterOrBigStepForward)', 'down': 'Action(ChapterOrBigStepBack)',
                'chup': 'Action(SkipNext)', 'chdown': 'Action(SkipPrevious)',
                'restart': 'Action(Rewind)', 'recall': 'Action(Number0)',
                'guide': 'ActivateWindow(TVGuide)', 'info': 'Action(Info)'}


def fallback_action(key, fb=None, d='0'):
    """What the key does when none of our channels is playing.

    'fb' carries the mapping another add-on's keymap had for this key (e.g. Xstream
    Pro's own channel-number entry); otherwise Kodi's normal action.
    """
    if fb:
        return fb if '(' in fb else 'Action(%s)' % fb
    if key == 'digit':
        return 'Action(Number%s)' % d
    return ZAP_FALLBACK.get(key, 'Noop')


def _recording_key(key):
    """Info / Guide while a catch-up recording from this add-on plays: the channel
    banner (with the recording) or the add-on's grid guide at that channel.
    Other keys keep their normal job (seeking) in recordings."""
    rec = playback.recording()
    if rec is None:
        return False
    catalog = Catalog(common.catalog_path())
    row = catalog.get('live', rec['id'])
    catalog.close()
    if row is None:
        return False
    if key == 'guide':
        from .guide import open_guide
        open_guide(playback.own_group(row), row['stream_id'])
    else:
        from . import overlay
        overlay.show_banner(row, 'Recording: %s' % rec.get('title') if rec.get('title') else 'Recording')
    return True


def handle(key='up', d='0', fb=None):
    """Remote keys in fullscreen video (called from the keymap).

    up/down/chup/chdown: change channel; restart: current show from its beginning;
    recall: previous channel; guide: grid guide. When none of our live channels is
    playing, the key does what Kodi normally does.
    """
    state = playback.zap_context()   # also while a just-tuned channel is opening
    if not state:
        if key in ('info', 'guide') and _recording_key(key):
            return
        return xbmc.executebuiltin(fallback_action(key, fb, d))
    from . import overlay
    if key == 'digit':
        return fullscreen_digit(state, d)
    if key == 'recall':
        row = playback.recall()
        if row is not None:
            overlay.show_banner(row, 'Previous channel')
        return
    if key == 'info':
        catalog = Catalog(common.catalog_path())
        row = catalog.get('live', state['id'])
        catalog.close()
        if row is not None:
            overlay.show_banner(row)
        return
    if key == 'guide':
        from .guide import open_guide
        return open_guide(state.get('cat') or '*', state.get('id'))
    if key == 'restart':
        if state.get('mode') == 'restart' or not common.setting_bool('zap_restart_key'):
            return xbmc.executebuiltin(fallback_action('restart', fb))   # already replaying: rewind
        catalog = Catalog(common.catalog_path())
        row = catalog.get('live', state['id'])
        catalog.close()
        if row is None or not row['archive']:
            return xbmc.executebuiltin(fallback_action('restart', fb))
        return playback.restart(row, state.get('cat'), confirm=True)
    player = xbmc.Player()
    step = 1 if key in ('up', 'chup') else -1
    if key in ('up', 'down') and common.setting_bool('zap_reverse'):
        step = -step
    catalog = Catalog(common.catalog_path())
    rows = live_rows(catalog, state['cat'])
    catalog.close()
    if not rows:
        return
    ids = [r['stream_id'] for r in rows]
    cursor = state.get('cursor') or state['id']
    idx = ids.index(cursor) if cursor in ids else (ids.index(state['id']) if state['id'] in ids else 0)
    skip = common.setting_int('offline_zap') == 0   # 0 = skip to next working, 1 = stay
    delay = common.setting_int('zap_debounce', 6) / 10.0
    # Pressing again soon after a channel change means "keep going": show each
    # channel at once but only tune the one you stop on, instead of opening and
    # closing every channel in between (each takes seconds to close).
    burst = delay > 0 and time.time() - state.get('t', 0) < ZAP_BURST
    if burst:
        return _zap_burst(state, rows, idx, step, skip, delay)
    return _zap_tune(state, rows, idx, step, skip)


ZAP_BURST = 4.0                                   # seconds since the last channel change
PROP_PRESS = common.ADDON_ID + '.zap_press'       # token of the newest key press


def _zap_burst(state, rows, idx, step, skip, delay):
    from . import overlay
    target = None
    for attempt in range(1, min(len(rows), 30) + 1):
        pos = (idx + step * attempt) % len(rows)
        row = rows[pos]
        if row['stream_id'] == state['id']:
            break
        if skip and playback.is_offline(row['stream_id']):
            continue
        target = (pos, row)
        break
    if target is None:
        return _zap_tune(state, rows, idx, step, skip)
    pos, row = target
    win = xbmcgui.Window(10000)
    token = uuid.uuid4().hex
    win.setProperty(PROP_PRESS, token)
    # The next press continues from this channel, even though it is not tuned yet.
    remember_zap(state['cat'], state['id'], cursor=row['stream_id'])

    def after_quiet():
        monitor = xbmc.Monitor()
        end = time.time() + delay
        while time.time() < end:
            if win.getProperty(PROP_PRESS) != token or monitor.waitForAbort(0.05):
                return                      # a newer key press took over
        if win.getProperty(PROP_PRESS) == token:
            _zap_tune(state, rows, (pos - step) % len(rows), step, skip, banner=False)
    overlay.show_banner(row, '%d of %d' % (pos + 1, len(rows)), during=after_quiet)


def _zap_tune(state, rows, idx, step, skip, banner=True):
    """Tune the next working channel after position `idx`."""
    from . import overlay
    player = xbmc.Player()
    cursor = state.get('cursor') or state['id']
    skipped = 0
    t_start = time.time()
    # The old stream has to go before the check: with it open the provider may
    # refuse the check (one-connection plans), which marked good channels offline.
    stopped = playback.free_connection()
    for attempt in range(1, min(len(rows), 30) + 1):
        pos = (idx + step * attempt) % len(rows)
        row = rows[pos]
        if row['stream_id'] == state['id']:
            break   # went all the way round
        if skip and playback.is_offline(row['stream_id']):
            skipped += 1
            continue
        if playback.check_live(row):
            common.log('Channel %s: ready to play %.1fs after the key press' % (
                row['name'], time.time() - t_start))
            remember_zap(state['cat'], row['stream_id'], row=row)
            path, li = live_item(row)
            xbmcgui.Window(10000).clearProperty(common.ADDON_ID + '.trakt_now')
            xbmcgui.Window(10000).setProperty(playback.PROP_TUNE_T, '%f' % t_start)
            extra = '%d of %d' % (pos + 1, len(rows))
            if skipped:
                extra += '   -   skipped %d offline' % skipped
            def tune():
                player.play(path, li)
                playback.watch_engine(row)
            if banner:   # banner first, then open the stream
                overlay.show_banner(row, extra, during=tune)
            else:
                tune()
            return
        if not skip:
            # Stay on the current channel; the next press continues past this one.
            playback.offline_notice(row['name'])
            if stopped:   # it was closed to free the connection: resume it
                current = next((r for r in rows if r['stream_id'] == state['id']), None)
                if current is not None:
                    path, li = live_item(current)
                    player.play(path, li)
            remember_zap(state['cat'], state['id'], cursor=row['stream_id'])
            return
        skipped += 1
    common.notify('No working channel found nearby', 3000)
    if stopped:   # nothing better found: go back to what was playing
        current = next((r for r in rows if r['stream_id'] == state['id']), None)
        if current is not None:
            path, li = live_item(current)
            player.play(path, li)


def fullscreen_digit(state, d):
    """Channel numbers typed while watching fullscreen; a lone 0 recalls."""
    from . import overlay
    catalog = Catalog(common.catalog_path())
    group = live_rows(catalog, state.get('cat') or '*')

    def lookup(n):
        for i, r in enumerate(group):
            if (r['num'] or (i + 1)) == n:
                return r
        return catalog.find_live_num(n)

    try:
        what, n = overlay.digit(d, lookup)
        row = lookup(n) if what == 'tune' else None
    finally:
        catalog.close()
    if what == 'recall':
        row = playback.recall()
        if row is not None:
            overlay.show_banner(row, 'Previous channel')
    elif what == 'tune':
        if row is None:
            return common.notify('No channel %d' % n, 2500)
        in_group = any(r['stream_id'] == row['stream_id'] for r in group)
        if playback.start_live(row, state.get('cat') if in_group else playback.own_group(row),
                               announce=False):
            overlay.show_banner(row)
