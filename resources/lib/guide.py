# -*- coding: utf-8 -*-
"""Grid TV guide: channels down the side, time across.

Kodi's own grid control only works with PVR add-ons, so the programme blocks are
buttons placed by this module, two hours (four half-hour columns) at a time.
"""
import os
import threading
import time

import xbmc
import xbmcgui

from . import common, playback, reminders, theme
from .catalog import Catalog, live_rows
from .epg import EPG
from .playback import picture_up

ROWS = 8
X0, WIDTH, Y0, ROW_H, GAP = 360, 1530, 180, 88, 4
SLOT = 30 * 60
SPAN = 4 * SLOT
LOGO, NAME, TIMES, NOW_LINE = 110, 120, 201, 300

ACTION_LEFT, ACTION_RIGHT, ACTION_UP, ACTION_DOWN = 1, 2, 3, 4
ACTION_PAGE_UP, ACTION_PAGE_DOWN = 5, 6
ACTION_CLOSE = (10, 92)
ACTION_CONTEXT = (117,)
ACTION_CH_UP, ACTION_CH_DOWN = 184, 185   # ACTION_CHANNEL_UP / ACTION_CHANNEL_DOWN

ALIGN = 0x00000004 | 0x00000008   # XBFONT_CENTER_Y | XBFONT_TRUNCATED
TICK = 10          # seconds between "now" line moves
MIN_REDRAW = 25    # do not rebuild the grid twice within this many seconds


def _star():
    return '[B]\u2022[/B] '


def now_wrapped(start, now=None):
    """True when 'now' has moved past the right edge of the time window."""
    return (now or time.time()) >= start + SPAN


def _media(skin):
    return os.path.join(common.ADDON_PATH, 'resources', 'skins', skin or 'default', 'media')


def _tex(skin):
    """(button, on-now button, focused button) textures of a skin folder.

    The programme blocks are buttons made in Python, so their colours come from
    the theme; the textures are tiny solid PNGs in the skin's media folder.
    """
    media = _media(skin)
    return (os.path.join(media, 'guide_btn.png'), os.path.join(media, 'guide_now.png'),
            os.path.join(media, 'guide_focus.png'))


class GuideWindow(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        self._playing_key = None   # catch-up / restart started from here
        self.cat_id = '*'
        self.select_id = None
        self.rows = []
        self.offset = 0          # first channel row shown
        self.start = 0           # left edge of the time window
        self.focus_row = 0
        self.focus_time = 0
        self.cells = []          # per visible row: [(button, programme)]
        self.by_id = {}          # control id -> (row, index)
        self.buttons = []
        self._ready = False
        self._stop = threading.Event()
        self.catalog = Catalog(common.catalog_path())
        self.guide = None
        self._theme = theme.current()
        self._skin = theme.skin_dir(self._theme)
        self._tex = _tex(self._skin)
        self._drawn = 0.0        # when the grid was last rebuilt

    def setup(self, cat_id, select_id=None):
        self.cat_id, self.select_id = cat_id or '*', select_id

    # ------------------------------------------------------------ setup
    def onInit(self):
        if self._ready:
            self._update_now_line()
            return
        self._ready = True
        playback.ui_opened()
        self.guide = EPG(common.epg_path())
        self.rows = live_rows(self.catalog, self.cat_id)
        if not self.rows:
            self.rows = live_rows(self.catalog, '*')
            self.cat_id = '*'
        now = time.time()
        self.start = int(now // SLOT * SLOT)
        idx = 0
        for i, r in enumerate(self.rows):
            if r['stream_id'] == self.select_id:
                idx = i
                break
        self.offset = max(0, min(idx, len(self.rows) - ROWS))
        self.focus_row = idx - self.offset
        self.focus_time = now
        name = 'All channels'
        if self.cat_id == 'fav':
            name = 'Favourites'
        elif self.cat_id != '*':
            name = self.catalog.category_names('live').get(self.cat_id, '')
        self.setProperty('header', 'TV guide  -  %s  [COLOR FF8A94A8](%d)[/COLOR]'
                         % (name, len(self.rows)))
        self.draw()
        self.focus_cell(self.focus_row, self.focus_time)
        threading.Thread(target=self._ticker, daemon=True).start()

    def _ticker(self):
        """Move the "now" line along; only rebuild the whole grid now and then
        (a rebuild makes hundreds of button controls)."""
        monitor = xbmc.Monitor()
        while not self._stop.wait(TICK) and not monitor.abortRequested():
            try:
                if now_wrapped(self.start):
                    self.start = int(time.time() // SLOT * SLOT)
                    self.draw()
                else:
                    self._update_now_line()
            except Exception:
                return

    # ------------------------------------------------------------- draw
    def draw(self):
        if self.buttons:
            self.removeControls(self.buttons)
        self.buttons, self.cells, self.by_id = [], [], {}
        self._drawn = time.time()
        t = self._theme
        tex_normal, tex_now, tex_focus = self._tex
        now = time.time()
        end = self.start + SPAN
        lt = time.localtime(self.start)
        if time.strftime('%Y%m%d', lt) == time.strftime('%Y%m%d'):
            self.setProperty('day', 'Today')
        else:
            self.setProperty('day', time.strftime('%a %d %b', lt))
        for k in range(4):
            self.getControl(TIMES + k).setLabel(common.fmt_time(self.start + k * SLOT))
        reminded = reminders.keys()
        favs = set(common.load_favs()) if self.cat_id != 'fav' else set()
        row_cells = []
        for r in range(ROWS):
            ci = self.offset + r
            logo, label = self.getControl(LOGO + r), self.getControl(NAME + r)
            cells = []
            if ci >= len(self.rows):
                logo.setImage('')
                label.setLabel('')
                row_cells.append(cells)
                continue
            row = self.rows[ci]
            logo.setImage(row['icon'] or '')
            name = '%s  %s' % (row['num'] or ci + 1, row['name'])
            label.setLabel(_star() + name if row['stream_id'] in favs else name)
            progs = self.guide.listings(row['epg_id'], self.start, end) if self.guide.ok else []
            if not progs:
                progs = [{'start': self.start, 'stop': end, 'title': 'No programme information',
                          'descr': '', 'noinfo': True}]
            y = Y0 + r * ROW_H
            for p in progs:
                x1 = X0 + max(0, p['start'] - self.start) * WIDTH / float(SPAN)
                x2 = X0 + min(SPAN, p['stop'] - self.start) * WIDTH / float(SPAN)
                w = int(x2 - x1) - GAP
                if w < 6:
                    continue
                airing = p['start'] <= now < p['stop'] or p.get('noinfo')
                if p['stop'] <= now:
                    colour = t.catchup if row['archive'] else t.dim   # catch-up / gone
                else:
                    colour = t.text
                title = p['title'] or 'No title'
                if reminders.key(row['stream_id'], p['start']) in reminded:
                    title = '» ' + title
                btn = xbmcgui.ControlButton(
                    int(x1), y, w, ROW_H - GAP, title,
                    focusTexture=tex_focus, noFocusTexture=tex_now if airing else tex_normal,
                    textOffsetX=12, alignment=ALIGN, font='font12',
                    textColor=colour, focusedColor=t.text_sel)
                cells.append((btn, p))
                self.buttons.append(btn)
            row_cells.append(cells)
        if self.buttons:
            self.addControls(self.buttons)
        for r, cells in enumerate(row_cells):
            for i, (btn, p) in enumerate(cells):
                self.by_id[btn.getId()] = (r, i)
        self.cells = row_cells
        self._update_now_line()

    def _update_now_line(self):
        now = time.time()
        line = self.getControl(NOW_LINE)
        if self.start <= now < self.start + SPAN:
            line.setPosition(int(X0 + (now - self.start) * WIDTH / float(SPAN)), Y0 - 8)
            line.setVisible(True)
        else:
            line.setVisible(False)

    # ------------------------------------------------------------ focus
    def focus_cell(self, r, t):
        if not self.cells:
            return
        r = max(0, min(r, len(self.cells) - 1))
        while r > 0 and not self.cells[r]:
            r -= 1
        cells = self.cells[r]
        if not cells:
            return
        pick = cells[-1]
        for btn, p in cells:
            if p['start'] <= t < p['stop'] or p['start'] >= t:
                pick = (btn, p)
                break
        self.focus_row = r
        self.setFocus(pick[0])
        self._show_info(r, pick[1])

    def _current(self):
        hit = self.by_id.get(self.getFocusId())
        if hit is None:
            return None
        r, i = hit
        return r, i, self.cells[r][i][1]

    def _show_info(self, r, p):
        row = self.rows[self.offset + r]
        when = '%s - %s' % (common.fmt_day_time(p['start']), common.fmt_time(p['stop']))
        now = time.time()
        tag = ''
        if p.get('noinfo'):
            when, tag = '', 'Press OK to watch'
        elif p['start'] <= now < p['stop']:
            tag = 'On now' + ('  -  OK: watch live or from the beginning' if row['archive'] else '')
        elif p['stop'] <= now:
            tag = 'Catch-up available' if row['archive'] else 'Already aired'
        else:
            tag = ('Reminder set  -  OK: remove' if reminders.has(row['stream_id'], p['start'])
                   else 'OK: set a reminder')
        self.setProperty('p_title', p['title'] or '')
        self.setProperty('p_time', '  |  '.join(x for x in (when, row['name'], tag) if x))
        self.setProperty('p_plot', p.get('descr') or '')

    # ---------------------------------------------------------- actions
    def onAction(self, action):
        aid = action.getId()
        if aid in ACTION_CLOSE:
            return self.close()
        cur = self._current()
        if cur is None:
            if aid in (ACTION_LEFT, ACTION_RIGHT, ACTION_UP, ACTION_DOWN):
                self.focus_cell(self.focus_row, self.focus_time)
            return
        r, i, p = cur
        if aid in ACTION_CONTEXT:
            return self._menu(r, p)
        if aid == ACTION_LEFT:
            if i > 0:
                p = self.cells[r][i - 1][1]
                self.focus_time = max(p['start'], self.start)
                self.focus_cell(r, self.focus_time)
            else:
                earliest = time.time() - self._max_past()
                if self.start - SLOT < earliest:
                    return
                self.start -= SLOT
                self.draw()
                cells = self.cells[r]
                target = [c for c in cells if c[1]['start'] < p['start']]
                self.focus_time = max(target[-1][1]['start'], self.start) if target else self.start
                self.focus_cell(r, self.focus_time)
        elif aid == ACTION_RIGHT:
            if i < len(self.cells[r]) - 1:
                p = self.cells[r][i + 1][1]
                self.focus_time = p['start']
                self.focus_cell(r, self.focus_time)
            else:
                if self.start + SLOT > time.time() + 7 * 86400:
                    return
                self.start += SLOT
                self.draw()
                self.focus_time = max(p['stop'], self.start)
                self.focus_cell(r, self.focus_time)
        elif aid in (ACTION_UP, ACTION_DOWN):
            step = -1 if aid == ACTION_UP else 1
            self.focus_time = max(p['start'], self.start)
            nr = r + step
            if nr < 0:
                if self.offset == 0:
                    return
                # Past the first line: show the previous page, cursor on its last line
                # (the channel just above the one we left).
                target = self.offset - 1
                self.offset = max(0, self.offset - ROWS)
                self.draw()
                nr = target - self.offset
            elif nr >= ROWS or self.offset + nr >= len(self.rows):
                if self.offset + ROWS >= len(self.rows):
                    return
                # Past the last line: show the next page, cursor on its first new line.
                target = self.offset + ROWS
                self.offset = min(self.offset + ROWS, max(0, len(self.rows) - ROWS))
                self.draw()
                nr = target - self.offset
            self.focus_cell(nr, self.focus_time)
        elif aid in (ACTION_PAGE_UP, ACTION_PAGE_DOWN, ACTION_CH_UP, ACTION_CH_DOWN):
            page = -ROWS if aid in (ACTION_PAGE_UP, ACTION_CH_UP) else ROWS
            new = max(0, min(self.offset + page, max(0, len(self.rows) - ROWS)))
            if new != self.offset:
                self.focus_time = max(p['start'], self.start)
                self.offset = new
                self.draw()
                self.focus_cell(r, self.focus_time)

    def _max_past(self):
        days = max([r['archive_days'] or 0 for r in self.rows] + [0])
        past = max(1, min(days, common.setting_int('epg_past_days', 7)))
        return past * 86400

    def onClick(self, control_id):
        hit = self.by_id.get(control_id)
        if hit is None:
            return
        r, i = hit
        self._select(r, self.cells[r][i][1])

    def _select(self, r, p, choice=None):
        row = self.rows[self.offset + r]
        now = time.time()
        if p.get('noinfo') or p['start'] <= now < p['stop']:
            # OK always means "watch live"; restarting is in the context menu
            # (and on the restart key once it plays), so no question here.
            if choice == 1:
                self._watch(('restart', row['stream_id'], p['start']), row['name'],
                            lambda: playback.restart(row, self.cat_id, windowed=True))
            else:
                self._watch(('live', row['stream_id']), row['name'],
                            lambda: playback.start_live(row, self.cat_id, windowed=True))
        elif p['stop'] <= now:
            if row['archive'] and p['start'] >= now - (row['archive_days'] or 0) * 86400:
                self._watch(('catchup', row['stream_id'], p['start']), row['name'],
                            lambda: playback.play_programme(row, p, windowed=True))
            else:
                common.notify('Catch-up is not available for this programme', 3000)
        else:
            reminders.toggle(row, p)
            self._redraw_keep(r, p)

    def _watch(self, key, name, start):   # name: kept for callers
        """First OK plays in the mini player and the guide stays open; OK on the
        same thing while it plays goes fullscreen (Back returns to the guide)."""
        if xbmc.Player().isPlayingVideo():
            # A live channel may have been changed in fullscreen since: ask what plays.
            st = playback.playing_context()
            current = ('live', st['id']) if st and not st.get('mode') else self._playing_key
        else:
            current = None
        if key == current:
            xbmc.executebuiltin('ActivateWindow(fullscreenvideo)')
            return
        if start():
            self._playing_key = key

    def _redraw_keep(self, r, p, force=False):
        """Rebuild the grid, keeping the cursor where it was.

        A rebuild makes one button per programme on screen, so quick presses (a
        reminder on, off, on...) are coalesced unless `force`."""
        if not force and time.time() - self._drawn < MIN_REDRAW:
            self.focus_cell(r, max(p['start'], self.start))
            self._show_info(r, p)
            return
        self.draw()
        self.focus_cell(r, max(p['start'], self.start))

    def _menu(self, r, p):
        row = self.rows[self.offset + r]
        options, acts = ['Watch %s live' % row['name']], [0]
        now = time.time()
        if row['archive'] and p['start'] <= now < p['stop']:
            options.append('Watch from the beginning')
            acts.append(1)
        if p['start'] > now:
            options.append('Remove reminder' if reminders.has(row['stream_id'], p['start'])
                           else 'Set reminder')
            acts.append(3)
        options.append('Jump to now')
        acts.append(2)
        is_fav = row['stream_id'] in common.load_favs()
        options.append('Remove from favourites' if is_fav else 'Add to favourites')
        acts.append(4)
        if xbmc.Player().isPlayingVideo():
            options.append('Watch fullscreen')   # whatever plays in the small window
            acts.append(5)
        c = xbmcgui.Dialog().contextmenu(options)
        if c < 0:
            return
        if acts[c] == 0:
            self._watch(('live', row['stream_id']), row['name'],
                        lambda: playback.start_live(row, self.cat_id, windowed=True))
        elif acts[c] == 1:
            self._watch(('restart', row['stream_id'], p['start']), row['name'],
                        lambda: playback.restart(row, self.cat_id, windowed=True))
        elif acts[c] == 3:
            reminders.toggle(row, p)
            self._redraw_keep(r, p)
        elif acts[c] == 5:
            xbmc.executebuiltin('ActivateWindow(fullscreenvideo)')
        elif acts[c] == 4:
            added = common.toggle_fav(row['stream_id'])
            common.notify('Added to favourites' if added else 'Removed from favourites', 2500)
            self._redraw_keep(r, p)
        else:
            self.start = int(now // SLOT * SLOT)
            self.draw()
            self.focus_time = now
            self.focus_cell(r, now)

    def close(self):
        self._stop.set()
        if getattr(self, '_ui_done', False):
            # Back already closed the window: xbmcgui.WindowXML.close() asks Kodi
            # for the previous window each time it is called, so calling it twice
            # would step two windows back (out of the guide and out of whatever
            # the guide was opened over, straight to Kodi's home screen).
            return
        self._ui_done = True
        # Closing the guide returns to whatever was underneath (Kodi's fullscreen
        # video or this add-on's TV mode), so the channel keeps playing.
        playback.ui_closed(keep_playing=getattr(self, 'keep_playing', False))
        xbmcgui.WindowXML.close(self)


def open_guide(cat_id='*', select_id=None, before_show=None, win=None):
    """win: reuse a GuideWindow (tests, or a caller that already made one)."""
    if win is None:
        win = GuideWindow(theme.GUIDE_XML, common.ADDON_PATH, theme.skin_dir(), '1080i')
    win.setup(cat_id, select_id)
    # Opened while a channel plays fullscreen: closing the guide returns to that
    # picture, so the channel keeps playing. Opened from the add-on's own menu
    # (or anywhere else) it is the last screen of the add-on: stop on exit.
    # The fullscreen video window decides, not Player.isPlayingVideo(): that is
    # true for a stream playing behind a list as well, and closing the guide
    # would then leave a channel playing with nobody watching. A guide over TV
    # mode needs no flag: TV mode is still open, so nothing is stopped.
    win.keep_playing = picture_up()
    below = playback.UI['win']
    playback.UI['win'] = win
    try:
        if before_show:
            before_show()
        win.doModal()
    finally:
        playback.UI['win'] = below
        win.close()
        if win.guide:
            win.guide.close()
        win.catalog.close()
        del win
