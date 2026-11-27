# -*- coding: utf-8 -*-
"""Background service: keeps channel lists and the full EPG up to date."""
import hashlib
import os
import time
import traceback

import xbmc
import xbmcgui

from resources.lib import common, keymap, library, playback, reminders, sync, trakt
from resources.lib.xtream import XtreamError

RETRY_AFTER = 30 * 60  # seconds before retrying a failed automatic update


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
    common.save_state(state)
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
        common.save_state(state)
        win.clearProperty(common.PROP_SYNCING)
        if dlg:
            dlg.close()


class Monitor(xbmc.Monitor):
    def __init__(self):
        super(Monitor, self).__init__()
        self.settings_changed = False

    def onSettingsChanged(self):
        self.settings_changed = True


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


def run():
    monitor = Monitor()
    scrobbler = trakt.Scrobbler()   # keep a reference: it receives playback callbacks
    recovery = playback.LiveRecovery()   # retries channels that fail to start
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
    while not monitor.abortRequested():
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
                    if state.get('attempt_creds') != h:
                        mode = 'full'
                elif (common.setting_int('epg_offset', 0) != state.get('epg_offset_built', 0)
                      and common.setting_bool('epg_enable') and os.path.exists(common.epg_path())
                      and state.get('offset_try') != common.setting_int('epg_offset', 0)):
                    mode = 'epg'   # time offset changed: rebuild the guide
                    state['offset_try'] = common.setting_int('epg_offset', 0)
                    common.save_state(state)
                elif common.setting_bool('bg_enable'):
                    interval = max(1, common.setting_int('refresh_hours', 12)) * 3600
                    if (now - state.get('last_sync', 0) >= interval
                            and now - state.get('last_attempt', 0) >= RETRY_AFTER):
                        mode = 'full'
            if mode:
                do_sync(monitor, win, mode)
        scrobbler.tick()
        reminders.check_sleep()
        for due in reminders.take_due(common.setting_int('reminder_lead', 1)):
            reminders.fire(due)
        trakt_sync_if_due()
        if monitor.waitForAbort(5):
            break


if __name__ == '__main__':
    run()
