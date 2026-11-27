# -*- coding: utf-8 -*-
"""TV mode: channel groups, channel list, mini player, now/next and schedule.

OK on a channel plays it in the small video window; OK again goes fullscreen.
Back from fullscreen returns here while the channel keeps playing.
"""
import json
import math
import threading
import time

import xbmc
import xbmcgui

from . import common
from .catalog import Catalog, live_rows
from .epg import EPG
from . import playback, reminders
from .playback import client
from .xtream import XtreamError

GROUPS, CHANNELS, SCHEDULE, PROG_FG = 100, 200, 500, 406
PROG_WIDTH = 830
ACTION_CLOSE = (10, 92)   # ACTION_PREVIOUS_MENU, ACTION_NAV_BACK
ACTION_CONTEXT = (117,)   # ACTION_CONTEXT_MENU (C key / long press)
ACTION_DIGITS = range(58, 68)   # ACTION_REMOTE_0 .. ACTION_REMOTE_9
ACTION_INFO = (11,)             # ACTION_SHOW_INFO: opens the grid guide
# Big groups (e.g. 40,000 channels in 'All channels') are shown as a window of
# VIEW channels around the cursor that moves as you scroll, so opening stays fast.
BIG_GROUP = 1500
VIEW = 800
UP, DOWN = 'up', 'down'
GREY = 'FF5A6478'


def _now_label(progs, now):
    if progs and progs[0]['start'] <= now < progs[0]['stop']:
        return progs[0]['title']
    return ''


class TVWindow(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        self.catalog = Catalog(common.catalog_path())
        self.groups = []
        self.rows = []
        self.cat_id = '*'
        self.playing_id = None
        self.sched = []
        self.sched_row = None
        self._last_pos = -1
        self._stop = threading.Event()
        self._thread = None
        self._ready = False
        self._digits = ''
        self._digit_timer = None
        self.index = {}          # stream_id -> index in self.rows
        self._labelled = set()   # row indexes whose now-playing label is filled
        self._grey = set()       # row indexes shown as offline
        self.view_start = 0      # first row index in the list control
        self.view_end = 0
        self.top_more = False
        self.bottom_more = False
        self._synced_id = None   # last channel the cursor followed
        self._favs = set()       # favourite channel ids (starred in the list)
        self._prog_key = None    # (channel, start) of a recording playing in the mini player
        self.base = ''

    # ------------------------------------------------------------ setup
    def onInit(self):
        if self._ready:     # back from fullscreen: just resync
            self._last_pos = -1
            # Kodi puts back the list position it saved when fullscreen opened, which
            # undoes any cursor move made meanwhile. Go to the channel last tuned
            # now, and let the worker do it once more after Kodi has finished.
            self._synced_id = None
            state = self._zap_state()
            sid = (state or {}).get('id')
            if sid in self.index:
                self._select_idx(self.index[sid])
            return
        self._ready = True
        t0 = time.time()
        # Clear a busy dialog an older version may have left on screen.
        xbmc.executebuiltin('Dialog.Close(busydialognocancel,true)')
        xbmc.executebuiltin('Dialog.Close(busydialog,true)')
        self.base = client().base
        self.groups_ctl = self.getControl(GROUPS)
        self.chan_ctl = self.getControl(CHANNELS)
        self.sched_ctl = self.getControl(SCHEDULE)
        self.prog_fg = self.getControl(PROG_FG)
        self.setProperty('header', common.ADDON_NAME)

        xbmcgui.Window(10000).setProperty(common.PROP_UI_OPEN, '1')
        autoplay = None
        state = self._zap_state()
        if state and self._our_live_playing():
            self.cat_id = state.get('cat') or '*'
            self.playing_id = state.get('id')
        elif not xbmc.Player().isPlaying() and common.setting_bool('tv_autoplay'):
            # Most recent channel that still exists and is not adult.
            for last in playback.history():
                if last.get('adult'):
                    continue
                row = self.catalog.get('live', last.get('id'))
                if row is not None and not row['adult']:
                    autoplay = row
                    self.cat_id = last.get('cat') or '*'
                    break
        self._synced_id = (state or {}).get('id')
        self.load_groups()
        t_groups = time.time()
        self.load_channels(self.cat_id, select_id=autoplay['stream_id'] if autoplay else self.playing_id)
        if autoplay is not None and not self.rows:
            self.load_channels('*', select_id=autoplay['stream_id'])
        self.setFocusId(CHANNELS)
        common.log('TV mode opened in %.1fs (groups %.1fs, channels %.1fs, %d channels)' % (
            time.time() - t0, t_groups - t0, time.time() - t_groups, len(self.rows)))
        self._thread = threading.Thread(target=self._worker, args=(autoplay,))
        self._thread.daemon = True
        self._thread.start()

    def load_groups(self, keep=False):
        self.groups = [{'id': '*', 'name': 'All channels'},
                       {'id': 'fav', 'name': 'Favourites', 'cnt': len(live_rows(self.catalog, 'fav'))}]
        self.groups += [{'id': c['id'], 'name': c['name'], 'cnt': c['cnt'],
                         'provider_name': c.get('provider_name', c['name'])}
                        for c in self.catalog.categories('live') if c['cnt']]
        sel_pos = self.groups_ctl.getSelectedPosition()
        items = []
        sel = 0
        counts = common.setting_bool('show_counts')   # read once: each read is slow on a box
        for i, g in enumerate(self.groups):
            label = g['name']
            if 'cnt' in g and counts:
                label += '  [COLOR FF8A94A8](%d)[/COLOR]' % g['cnt']
            li = xbmcgui.ListItem(label, offscreen=True)
            if g['id'] == self.cat_id:
                li.setProperty('active', 'true')
                sel = i
            items.append(li)
        self.groups_ctl.reset()
        self.groups_ctl.addItems(items)
        self.groups_ctl.selectItem(sel_pos if keep and 0 <= sel_pos < len(items) else sel)

    def load_channels(self, cat_id, select_id=None):
        self.cat_id = cat_id
        self._favs = set(common.load_favs()) if cat_id != 'fav' else set()
        rows = live_rows(self.catalog, cat_id)
        index = {}
        for i, r in enumerate(rows):
            index.setdefault(r['stream_id'], i)
        self.rows = rows
        self.index = index
        sel = index.get(select_id, 0) if select_id else 0
        self._build_view(sel)
        self._last_pos = -1
        for i in range(self.groups_ctl.size()):
            self.groups_ctl.getListItem(i).setProperty(
                'active', 'true' if self.groups[i]['id'] == cat_id else '')
        name = next((g['name'] for g in self.groups if g['id'] == cat_id), '')
        self.setProperty('header', '%s  -  %s  [COLOR FF8A94A8](%d)[/COLOR]'
                         % (common.ADDON_NAME, name, len(rows)))

    def _build_view(self, sel):
        """Fill the list control with the rows around index `sel` and select it."""
        rows = self.rows
        if len(rows) > BIG_GROUP:
            start = max(0, min(sel - VIEW // 2, len(rows) - VIEW))
            end = min(len(rows), start + VIEW)
        else:
            start, end = 0, len(rows)
        self.view_start, self.view_end = start, end
        self.top_more, self.bottom_more = start > 0, end < len(rows)
        offline = playback.offline_ids()
        items = []
        if self.top_more:
            items.append(xbmcgui.ListItem('[COLOR FF8A94A8][ %d earlier channels ][/COLOR]' % start,
                                          offscreen=True))
        self._grey = set()
        for i in range(start, end):
            r = rows[i]
            label = self._name(i)
            if r['stream_id'] in offline:
                li = xbmcgui.ListItem('[COLOR %s]%s[/COLOR]' % (GREY, label),
                                      '[COLOR %s]Offline[/COLOR]' % GREY, offscreen=True)
                self._grey.add(i)
            else:
                li = xbmcgui.ListItem(label, offscreen=True)
            li.setArt({'icon': r['icon'] or 'DefaultAddonPVRClient.png'})
            if r['stream_id'] == self.playing_id:
                li.setProperty('playing', 'true')
            items.append(li)
        if self.bottom_more:
            items.append(xbmcgui.ListItem('[COLOR FF8A94A8][ %d more channels ][/COLOR]'
                                          % (len(rows) - end), offscreen=True))
        self._labelled = set()
        self.chan_ctl.reset()
        self.chan_ctl.addItems(items)
        if rows:
            pos = self._idx_to_pos(min(max(sel, start), end - 1))
            self.chan_ctl.selectItem(pos)
            guide = EPG(common.epg_path())
            try:
                self._fill_labels(guide, min(max(sel, start), end - 1))
            finally:
                guide.close()

    # positions in the list control <-> indexes in self.rows
    def _idx_to_pos(self, idx):
        if idx is None or not self.view_start <= idx < self.view_end:
            return None
        return idx - self.view_start + (1 if self.top_more else 0)

    def _pos_to_idx(self, pos):
        if pos is None or pos < 0:
            return None
        if self.top_more and pos == 0:
            return UP
        idx = self.view_start + pos - (1 if self.top_more else 0)
        if idx >= self.view_end:
            return DOWN if self.bottom_more else None
        return idx

    def _selected_idx(self):
        idx = self._pos_to_idx(self.chan_ctl.getSelectedPosition())
        return idx if isinstance(idx, int) else None

    def _select_idx(self, idx):
        """Move the cursor to row `idx`, shifting the window if needed."""
        pos = self._idx_to_pos(idx)
        if pos is None:
            self._build_view(idx)
        else:
            self.chan_ctl.selectItem(pos)

    def _shift(self, direction):
        """The cursor reached '[ earlier/more channels ]': move the window along."""
        target = self.view_start - 1 if direction == UP else self.view_end
        self._build_view(target)

    # ---------------------------------------------------------- helpers
    def _name(self, idx):
        """'12  Channel name', starred if it is a favourite."""
        row = self.rows[idx]
        label = '%s  %s' % (row['num'] or (idx + 1), row['name'])
        return common.STAR + label if row['stream_id'] in self._favs else label

    def _label(self, li, idx, offline, now_title=None):
        """Normal or greyed-out (offline) label for row `idx`."""
        row = self.rows[idx]
        label = self._name(idx)
        if row['stream_id'] in offline:
            li.setLabel('[COLOR %s]%s[/COLOR]' % (GREY, label))
            li.setLabel2('[COLOR %s]Offline[/COLOR]' % GREY)
            self._grey.add(idx)
        else:
            li.setLabel(label)
            if now_title is not None or idx in self._grey:
                li.setLabel2(now_title or '')
            self._grey.discard(idx)

    def _relabel(self, stream_id):
        idx = self.index.get(stream_id)
        pos = self._idx_to_pos(idx)
        if pos is not None and pos < self.chan_ctl.size():
            self._label(self.chan_ctl.getListItem(pos), idx, playback.offline_ids())

    def _fill_labels(self, guide, center, force=False, radius=60):
        """Fill 'now playing' labels around row `center` (big lists stay fast)."""
        rows = self.rows
        lo, hi = max(self.view_start, center - radius), min(self.view_end, center + radius)
        todo = [i for i in range(lo, hi) if force or i not in self._labelled]
        if not todo:
            return
        nn = guide.now_next([rows[i]['epg_id'] for i in todo], count=1)
        offline = playback.offline_ids()
        now = time.time()
        size = self.chan_ctl.size()
        if force:
            self._labelled = set()
        for i in todo:
            pos = self._idx_to_pos(i)
            if pos is not None and pos < size:
                self._label(self.chan_ctl.getListItem(pos), i, offline,
                            _now_label(nn.get(rows[i]['epg_id']), now))
                self._labelled.add(i)

    def _zap_state(self):
        raw = xbmcgui.Window(10000).getProperty(common.PROP_ZAP)
        try:
            return json.loads(raw) if raw else None
        except ValueError:
            return None

    def _our_live_playing(self):
        """One of our channels is playing (live, or restarted from the beginning)."""
        return playback.playing_context(self.base or None) is not None

    def _mark_playing(self, sid, select=False):
        if sid is not None:
            self._prog_key = None      # a channel replaced the recording
        old, self.playing_id = self.playing_id, sid
        size = self.chan_ctl.size()
        pos = self._idx_to_pos(self.index.get(old))
        if pos is not None and pos < size:
            self.chan_ctl.getListItem(pos).setProperty('playing', '')
        idx = self.index.get(sid)
        if idx is not None and select:
            self._select_idx(idx)
        pos = self._idx_to_pos(idx)
        if pos is not None and pos < self.chan_ctl.size():
            self.chan_ctl.getListItem(pos).setProperty('playing', 'true')

    # ---------------------------------------------------------- actions
    def onAction(self, action):
        aid = action.getId()
        if aid in ACTION_CLOSE:
            if self._digits:          # Back cancels a half-typed number
                self._clear_digits()
            else:
                self.close()
        elif aid in ACTION_DIGITS:
            self._digit(aid - 58)
        elif aid in ACTION_CONTEXT and self.getFocusId() == CHANNELS:
            self._channel_menu()
        elif aid in ACTION_CONTEXT and self.getFocusId() == GROUPS:
            self._group_menu()
        elif aid in ACTION_INFO:
            self.open_grid()

    def open_grid(self):
        from .guide import open_guide
        idx = self._selected_idx()
        sel = self.rows[idx]['stream_id'] if idx is not None else self.playing_id
        open_guide(self.cat_id, sel)
        self._last_pos = -1

    # ------------------------------------------------ number entry
    def _find_num(self, n):
        """Channel number n: current group first (as numbered there), then all."""
        for i, r in enumerate(self.rows):
            if (r['num'] or (i + 1)) == n:
                return r
        return self.catalog.find_live_num(n) if n > 0 else None

    def _digit(self, d):
        self._digits = (self._digits + str(d))[-5:]
        n = int(self._digits)
        row = self._find_num(n)
        self.setProperty('digits', self._digits)
        if self._digits == '0':
            prev = (playback.zap_state() or {}).get('prev')
            prow = self.catalog.get('live', prev) if prev else None
            self.setProperty('digits_name', 'Previous: %s' % prow['name'] if prow else 'Previous channel')
        else:
            self.setProperty('digits_name', row['name'] if row else 'No channel %d' % n)
        if self._digit_timer:
            self._digit_timer.cancel()
        self._digit_timer = threading.Timer(2.0, self._digit_go)
        self._digit_timer.daemon = True
        self._digit_timer.start()

    def _clear_digits(self):
        if self._digit_timer:
            self._digit_timer.cancel()
        self._digits = ''
        self.setProperty('digits', '')
        self.setProperty('digits_name', '')

    def _digit_go(self):
        typed = self._digits
        n = int(typed or 0)
        self._clear_digits()
        if self._stop.is_set():
            return
        if typed == '0':   # 0 on its own = channel recall
            row = playback.recall(windowed=True)
            if row is not None:
                self._relabel(row['stream_id'])
                self._mark_playing(row['stream_id'], select=True)
            return
        row = self._find_num(n)
        if row is None:
            return
        if row['stream_id'] not in self.index:
            self.load_channels('*', select_id=row['stream_id'])
        else:
            self._select_idx(self.index[row['stream_id']])
        self.play_channel(row)

    # ------------------------------------------------ context menu
    def _group_menu(self):
        from . import groups
        pos = self.groups_ctl.getSelectedPosition()
        if not 0 <= pos < len(self.groups):
            return
        from . import customize
        gid = self.groups[pos]['id']
        options = ['Show/hide groups...']
        if gid not in ('*', 'fav'):
            options = ['Rename group', 'Move group...', 'Hide this group'] + options
        if common.setting_bool('hide_adult') and common.pin_set():
            options.append('Hide adult content again' if common.adult_unlocked_until()
                           else 'Show adult content (PIN)')
        choice = xbmcgui.Dialog().contextmenu(options)
        if choice < 0:
            return
        picked = options[choice]
        if picked == 'Hide this group':
            groups.hide_group('live', gid)
            common.notify('Group hidden', 2500)
        elif picked == 'Rename group':
            g = self.groups[pos]
            if not customize.rename_group('live', gid, g['name'], g.get('provider_name', g['name'])):
                return
        elif picked == 'Move group...':
            real = [g for g in self.groups if g['id'] not in ('*', 'fav')]
            if not customize.move_group('live', real, gid):
                return
        elif picked == 'Show adult content (PIN)':
            if not common.unlock_adult():
                return
            self.catalog.hide_adult = common.adult_hidden()
        elif picked == 'Hide adult content again':
            common.lock_adult()
            self.catalog.hide_adult = common.adult_hidden()
        elif not groups.manage('live'):
            return
        self.catalog.hidden = common.load_hidden()
        if self.cat_id in self.catalog.hidden.get('live', set()):
            self.cat_id = '*'
        self.load_groups()
        self.load_channels(self.cat_id, select_id=self.playing_id)

    def _channel_menu(self):
        idx = self._selected_idx()
        if idx is None:
            return
        row = self.rows[idx]
        is_fav = row['stream_id'] in common.load_favs()
        options = ['Remove from favourites' if is_fav else 'Add to favourites',
                   'Watch fullscreen', 'TV guide (grid)', 'Sleep timer', 'Move channel...']
        if row['archive']:
            options.append('Watch from the beginning')
        choice = xbmcgui.Dialog().contextmenu(options)
        if choice == 2:
            return self.open_grid()
        if choice == 3:
            return xbmc.executebuiltin('RunPlugin(plugin://%s/?action=sleep_timer)' % common.ADDON_ID)
        if choice == 4:
            from . import customize
            if customize.move_channel(self.cat_id, self.rows, row['stream_id']):
                self.load_channels(self.cat_id, select_id=row['stream_id'])
            return
        if choice == 5:
            return self.restart(row)
        if choice == 0:
            added = common.toggle_fav(row['stream_id'])
            common.notify('Added to favourites' if added else 'Removed from favourites', 2500)
            self.load_groups(keep=True)
            if self.cat_id == 'fav':
                self.load_channels('fav', select_id=self.playing_id)
            else:
                self._favs = set(common.load_favs())
                self._relabel(row['stream_id'])
        elif choice == 1:
            if not (row['stream_id'] == self.playing_id and self._our_live_playing()):
                self.play_channel(row)
            xbmc.executebuiltin('ActivateWindow(fullscreenvideo)')

    def close(self):
        self._stop.set()
        xbmcgui.Window(10000).clearProperty(common.PROP_UI_OPEN)
        if common.setting_bool('tv_stop_on_exit'):
            player = xbmc.Player()
            try:
                if player.isPlaying() and player.getPlayingFile().startswith(client().base + '/'):
                    player.stop()
            except RuntimeError:
                pass
        if self._digit_timer:
            self._digit_timer.cancel()
        xbmcgui.WindowXML.close(self)

    def onClick(self, control_id):
        if control_id == GROUPS:
            pos = self.groups_ctl.getSelectedPosition()
            if 0 <= pos < len(self.groups):
                self.load_channels(self.groups[pos]['id'], select_id=self.playing_id)
                self.setFocusId(CHANNELS)
        elif control_id == CHANNELS:
            idx = self._pos_to_idx(self.chan_ctl.getSelectedPosition())
            if idx in (UP, DOWN):
                return self._shift(idx)
            if idx is not None:
                row = self.rows[idx]
                if row['stream_id'] == self.playing_id and self._our_live_playing():
                    xbmc.executebuiltin('ActivateWindow(fullscreenvideo)')
                else:
                    self.play_channel(row)
        elif control_id == SCHEDULE:
            pos = self.sched_ctl.getSelectedPosition()
            if not (0 <= pos < len(self.sched)) or self.sched_row is None:
                return
            p, row, now = self.sched[pos], self.sched_row, time.time()
            if p['start'] <= now < p['stop']:
                # OK means "watch live" (restart is in the channel menu): no question.
                if row['stream_id'] == self.playing_id and self._our_live_playing():
                    xbmc.executebuiltin('ActivateWindow(fullscreenvideo)')
                else:
                    self.play_channel(row)
            elif p['stop'] <= now and row['archive']:
                key = (row['stream_id'], p['start'])
                if key == self._prog_key and xbmc.Player().isPlayingVideo():
                    xbmc.executebuiltin('ActivateWindow(fullscreenvideo)')   # OK again
                else:
                    self.play_catchup(row, p)
            else:
                from . import reminders
                reminders.toggle(row, p)
                self._last_pos = -1   # redraw the schedule

    def play_channel(self, row):
        ok = playback.start_live(row, self.cat_id, windowed=True)
        self._relabel(row['stream_id'])
        if ok:
            self._mark_playing(row['stream_id'])
        return ok

    def play_catchup(self, row, p):
        if playback.play_programme(row, p, windowed=True):
            self._mark_playing(None)
            self._prog_key = (row['stream_id'], p['start'])

    def restart(self, row):
        if playback.restart(row, self.cat_id, windowed=True):
            self._mark_playing(row['stream_id'])

    # ----------------------------------------------------------- worker
    def _worker(self, autoplay=None):
        monitor = xbmc.Monitor()
        guide = EPG(common.epg_path())
        last_refresh = time.time()
        try:
            if autoplay is not None and not self._stop.is_set():
                self.play_channel(autoplay)   # after the window is up, so it never blocks it
            while not self._stop.is_set() and not monitor.abortRequested():
                # Follow channel changes made elsewhere (Up/Down or numbers in
                # fullscreen, the guide, a failed start): the cursor goes to the
                # channel last tuned, even if it is not playing any more.
                state = self._zap_state()
                sid = state.get('id') if state else None
                if sid and sid != self._synced_id:
                    self._synced_id = sid
                    if sid in self.index:
                        self._select_idx(self.index[sid])
                if sid and sid != self.playing_id and self._our_live_playing():
                    self._mark_playing(sid)
                rows = self.rows
                idx = self._pos_to_idx(self.chan_ctl.getSelectedPosition())
                if idx in (UP, DOWN):
                    self._shift(idx)
                    continue
                if idx is not None and idx != self._last_pos:
                    self._last_pos = idx
                    self._fill_labels(guide, idx)
                    self._show_channel(guide, rows[idx])
                elif time.time() - last_refresh > 60:
                    last_refresh = time.time()
                    if idx is not None:
                        self._fill_labels(guide, idx, force=True)
                        self._show_channel(guide, rows[idx], keep_selection=True)
                self._stop.wait(0.25)
        except Exception as e:   # window closed underneath us
            common.log('TV window worker stopped: %s' % e)
        finally:
            guide.close()

    def _show_channel(self, guide, row, keep_selection=False):
        now = time.time()
        name = row['name']
        if row['archive']:
            name += '  [COLOR FFFF9F1C]catch-up %dd[/COLOR]' % (row['archive_days'] or 0)
        self.setProperty('ch_name', name)
        past = 24 * 3600 if row['archive'] else 2 * 3600
        progs = guide.listings(row['epg_id'], now - past, now + 24 * 3600)
        cur = next((p for p in progs if p['start'] <= now < p['stop']), None)
        if cur:
            self.setProperty('now_line', '%s - %s   %s' % (
                common.fmt_time(cur['start']), common.fmt_time(cur['stop']), cur['title']))
            self.setProperty('now_plot', cur.get('descr') or '')
            self.setProperty('has_now', '1')
            pct = (now - cur['start']) / float(max(1, cur['stop'] - cur['start']))
            self.prog_fg.setWidth(max(1, int(PROG_WIDTH * min(pct, 1.0))))
        else:
            self.setProperty('now_line', 'No guide information' if not progs else '')
            self.setProperty('now_plot', '')
            self.setProperty('has_now', '')

        old_pos = self.sched_ctl.getSelectedPosition()
        items = []
        sel = 0
        for i, p in enumerate(progs):
            when = common.fmt_day_time(p['start'])
            if p['start'] <= now < p['stop']:
                label, tag, sel = '[B]%s  %s[/B]' % (when, p['title']), '[COLOR FF4FA3FF]NOW[/COLOR]', i
            elif p['stop'] <= now:
                if row['archive']:
                    label, tag = '%s  %s' % (when, p['title']), '[COLOR FFFF9F1C]CATCH-UP[/COLOR]'
                else:
                    label, tag = '[COLOR FF5A6478]%s  %s[/COLOR]' % (when, p['title']), ''
            else:
                label, tag = '%s  %s' % (when, p['title']), ''
                if p['start'] > now and reminders.has(row['stream_id'], p['start']):
                    tag = '[COLOR FF8A94A8]REMINDER[/COLOR]'
            items.append(xbmcgui.ListItem(label, tag, offscreen=True))
        self.sched = progs
        self.sched_row = row
        self.sched_ctl.reset()
        if items:
            self.sched_ctl.addItems(items)
            self.sched_ctl.selectItem(old_pos if keep_selection and 0 <= old_pos < len(items)
                                      else sel)


def open_tv(before_show=None):
    win = TVWindow('script-xtreamcodes-tv.xml', common.ADDON_PATH, 'default', '1080i')
    playback.UI['win'] = win
    try:
        if before_show:
            before_show()
        win.doModal()
    finally:
        playback.UI['win'] = None
        win._stop.set()
        xbmcgui.Window(10000).clearProperty(common.PROP_UI_OPEN)
        win.catalog.close()
        del win
