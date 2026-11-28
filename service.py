# -*- coding: utf-8 -*-
"""Background service: keeps channel lists and the full EPG up to date."""
import hashlib
import os
import threading
import time
import traceback

import xbmc
import xbmcgui

from resources.lib import common, keymap, library, playback, reminders, sync, trakt
from resources.lib.xtream import XtreamError

RETRY_AFTER = 30 * 60  # seconds before retrying a failed automatic update
# last attempt (time, creds) also kept in memory: if state.json cannot be saved
# (storage full or read-only) the service must not retry every 5 seconds
LAST_TRY = [0.0, None]


def creds_hash():
    raw = '|'.join((common.setting('server').strip(), common.setting('username').strip(),
                    common.setting('password').strip()))
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()


def do_sync(monitor, win, mode):
    notify = common.setting_bool('bg_notify')
    dlg = None
    if notify:
        dlg = xbmcgui.DialogProgressBG()
        dlg.create(common.ADDON_NAME, 'Updating...')

    def progress(pct, msg):
        if dlg:
            dlg.update(max(0, min(100, pct)), common.ADDON_NAME, msg)

    win.setProperty(common.PROP_SYNCING, '1')
    h = creds_hash()
    state = common.load_state()
    state.update(last_attempt=time.time(), attempt_creds=h)
    LAST_TRY[:] = [state['last_attempt'], h]
    try:
        common.save_state(state)
    except OSError as e:
        common.log('Could not save the update state: %s' % e, xbmc.LOGWARNING)
    try:
        result = sync.run_sync(mode, progress, abort=monitor.abortRequested)
        now = time.time()
        if mode in ('full', 'catalog'):
            state['last_sync'] = now
            state['creds'] = h
            if common.setting_bool('lib_auto_update'):
                try:
                    added = library.update_all()
                    if added:
                        library.scan()
                        result['library'] = added
                except Exception as e:
                    common.log('Library update failed: %s' % e, xbmc.LOGWARNING)
        if 'programmes' in result:
            state['last_epg'] = now
            state['epg_offset_built'] = result.get('epg_offset', 0)
        state['last_error'] = ''
        common.log('Update finished: %s' % result)
        if notify:
            parts = []
            if 'live' in result:
                parts.append('%d channels, %d movies, %d series' % (
                    result['live'], result['vod'], result['series']))
            if 'programmes' in result:
                parts.append('%d EPG entries' % result['programmes'])
            common.notify('Updated: ' + '; '.join(parts) if parts else 'Updated')
    except common.Aborted:
        common.log('Update aborted')
    except XtreamError as e:
        state['last_error'] = str(e)
        common.log('Update failed: %s' % e, xbmc.LOGWARNING)
        if notify:
            common.notify('Update failed: %s' % e, 8000)
    except Exception as e:  # keep the service alive whatever happens
        state['last_error'] = str(e)
        common.log('Update crashed: %s' % traceback.format_exc(), xbmc.LOGERROR)
        if notify:
            common.notify('Update failed: %s' % e, 8000)
    finally:
        try:
            common.save_state(state)
        except OSError as e:   # e.g. storage went read-only: keep the service alive
            common.log('Could not save the update state: %s' % e, xbmc.LOGWARNING)
        win.clearProperty(common.PROP_SYNCING)
        if dlg:
            dlg.close()


class Monitor(xbmc.Monitor):
    def __init__(self):
        super(Monitor, self).__init__()
        self.settings_changed = False

    def onSettingsChanged(self):
        self.settings_changed = True


class KeyListener(xbmc.Monitor):
    """Remote keys in fullscreen live TV, sent by the keymap with NotifyAll.

    The service is already running with everything loaded, so the channel banner
    appears at once instead of after starting the add-on for every key press.
    Kodi only delivers a Monitor's callbacks to the thread that created it, while
    that thread waits in waitForAbort(), so this runs in a thread of its own: key
    presses are handled even while the main loop is busy with a long update.
    """

    def onNotification(self, sender, method, data):
        if sender != common.ADDON_ID or not method.startswith('Other.'):
            return
        hit = keymap.resolve(method[len('Other.'):])
        if hit is None:
            return
        key, d, fb = hit
        # each press in its own thread, like separate add-on calls: the banner
        # holds its thread for a few seconds and a newer press takes over
        threading.Thread(target=self._handle, args=(key, d, fb), daemon=True).start()

    @staticmethod
    def _handle(key, d, fb):
        from resources.lib import zapper
        try:
            zapper.handle(key, d, fb)
        except Exception:
            common.log('Key %s failed: %s' % (key, traceback.format_exc()), xbmc.LOGERROR)


STOP = threading.Event()   # set when the service ends, so the key thread ends too


def listen_keys():
    listener = KeyListener()
    win = xbmcgui.Window(10000)
    win.setProperty(common.ADDON_ID + '.keys_ready', '1')
    try:
        while not STOP.is_set() and not listener.waitForAbort(1):
            pass
    finally:
        win.clearProperty(common.ADDON_ID + '.keys_ready')


def apply_keymap():
    try:
        keymap.apply()
    except Exception as e:
        common.log('Keymap update failed: %s' % e, xbmc.LOGWARNING)


def trakt_sync_if_due():
    if not trakt.linked():
        return
    state = common.load_state()
    now = time.time()
    if now - state.get('trakt_sync', 0) < trakt.SYNC_EVERY or now - state.get('trakt_try', 0) < 600:
        return
    state['trakt_try'] = now
    try:
        movies, shows = trakt.sync_watched()
        state['trakt_sync'] = now
        common.log('Trakt sync: %d movies, %d shows' % (movies, shows))
    except trakt.TraktError as e:
        common.log('Trakt sync failed: %s' % e, xbmc.LOGWARNING)
    except Exception:
        common.log('Trakt sync crashed: %s' % traceback.format_exc(), xbmc.LOGERROR)
    common.save_state(state)


def tick(monitor, win, scrobbler):
    """One pass of the service loop (every 5 s)."""
    if monitor.settings_changed:
        monitor.settings_changed = False
        apply_keymap()
    mode = win.getProperty(common.PROP_REQUEST) or None
    if mode:
        win.clearProperty(common.PROP_REQUEST)
    if common.is_configured():
        if not mode:
            state = common.load_state()
            now = time.time()
            h = creds_hash()
            if state.get('creds') != h:
                # New/changed account: refresh once (don't hammer a bad login).
                if state.get('attempt_creds') != h and LAST_TRY[1] != h:
                    mode = 'full'
            elif (common.setting_int('epg_offset', 0) != state.get('epg_offset_built', 0)
                  and common.setting_bool('epg_enable') and os.path.exists(common.epg_path())
                  and state.get('offset_try') != common.setting_int('epg_offset', 0)):
                mode = 'epg'   # time offset changed: rebuild the guide
                state['offset_try'] = common.setting_int('epg_offset', 0)
                common.save_state(state)
            elif common.setting_bool('bg_enable'):
                interval = max(1, common.setting_int('refresh_hours', 12)) * 3600
                last_try = max(state.get('last_attempt', 0), LAST_TRY[0])
                if (now - state.get('last_sync', 0) >= interval
                        and now - last_try >= RETRY_AFTER):
                    mode = 'full'
        if mode:
            do_sync(monitor, win, mode)
    if playback.left_addon():
        playback.stop_on_exit()
    scrobbler.tick()
    reminders.check_sleep()
    for due in reminders.take_due(common.setting_int('reminder_lead', 1)):
        reminders.fire(due)
    trakt_sync_if_due()


def run():
    monitor = Monitor()
    scrobbler = trakt.Scrobbler()   # keep a reference: it receives playback callbacks
    recovery = playback.LiveRecovery()   # retries channels that fail to start
    threading.Thread(target=listen_keys, name='keys', daemon=True).start()
    reminders.clean_temp_files()
    apply_keymap()
    win = xbmcgui.Window(10000)
    win.clearProperty(common.PROP_SYNCING)
    if monitor.waitForAbort(3):
        return
    if (common.setting_bool('tv_on_startup') and common.is_configured()
            and os.path.exists(common.catalog_path())):
        xbmc.executebuiltin('RunPlugin(plugin://%s/?action=tv)' % common.ADDON_ID)
    if monitor.waitForAbort(12):   # let Kodi finish starting up
        return
    try:
        while not monitor.abortRequested():
            try:
                tick(monitor, win, scrobbler)
            except Exception:   # never let one bad pass stop updates, reminders, keys
                common.log('Service pass failed: %s' % traceback.format_exc(), xbmc.LOGERROR)
            if monitor.waitForAbort(5):
                break
    finally:
        STOP.set()


if __name__ == '__main__':
    run()
