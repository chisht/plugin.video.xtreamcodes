"""STBEmu skin end to end: TV mode, the grid guide and the zapping banner.

Runs the real TV mode window and the real guide against the small fake server,
with the skin setting on STBEmu, and checks that the theme's colours reach the
list labels and the programme blocks, that the layout files come from the
resources/skins/stbemu folder and that the windows still behave as before.

Run from the repo root: python3 tests/skin_stbemu_test.py
"""
import os
import re
import sys
import tempfile
import time

ADDON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR'] = ADDON; os.environ['PROFILE_DIR'] = tempfile.mkdtemp()
sys.path[:0] = [os.path.join(ADDON, 'tests', 'stubs'), os.path.join(ADDON, 'tests'), ADDON]
import fake_server_skin as server   # noqa: E402
import xbmcaddon, xbmcgui, xbmc   # noqa: E402

srv = server.start()
S = xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d' % srv.server_address[1], username='u', password='p@ss',
         epg_enable='true', epg_past_days='2', hide_adult='true', show_counts='true',
         page_size='0', check_stream='false', check_timeout='3', offline_zap='0',
         mark_offline='true', live_format='0', skin='1',
         tv_autoplay='false', zap_debounce='0', zap_reverse='false')

from resources.lib import sync, guide, overlay, playback, theme, tvwindow   # noqa: E402
from resources.lib.catalog import Catalog, live_rows                        # noqa: E402

fails = 0


def check(name, ok):
    global fails
    fails += not ok
    print('%s %s' % ('PASS' if ok else 'FAIL', name))


def colours(text):
    return re.findall(r'\[COLOR ([0-9A-Fa-f]{8})\]', text)


sync.run_sync('full')
t = theme.current()
check('skin setting picks the STBEmu palette', t.name == 'stbemu' and t.accent == 'FFE08A1E')
check('layouts come from the STBEmu folder',
      theme.skin_dir() == 'stbemu' and theme.TV_XML.endswith('-tv.xml'))

# ------------------------------------------------------------- TV mode
w = tvwindow.TVWindow(theme.TV_XML, ADDON, theme.skin_dir(), '1080i')
w.onInit()
time.sleep(0.4)
g, c, s = w.getControl(100), w.getControl(200), w.getControl(500)
check('TV mode opened with the fake lineup (%s)' % [i.label for i in c.items],
      len(c.items) == 4 and c.items[0].label == '1  News One')
check('group list has its counts', 'News' in g.items[2].label and '(2)' in g.items[2].label)
check('header shows the channel count', '4' in w._props['header'])
check('now/next filled for the highlighted channel: %s' % w._props.get('now_line'),
      bool(w._props.get('now_line')))
check('progress bar is inside its track',
      0 < w.getControl(406).width <= tvwindow.PROG_WIDTH)
check('schedule lists programmes: %s' % [i.label for i in s.items[:2]],
      len(s.items) > 3 and s.items[s.sel].getLabel2().startswith('[COLOR FFE08A1E]NOW'))

# the theme's colours are what the labels carry
w.chan_ctl.selectItem(3)                  # what Kodi does on Down: cursor on row 3 (Kids)
check('the cursor moved to the last row (%s)' % c.items[3].label,
      w._pos_to_idx(w.chan_ctl.getSelectedPosition()) == 3)
playback.set_offline('104', True)
w._last_pos = -1
epg = guide.EPG(playback.common.epg_path())
try:
    w._fill_labels(epg, 3, force=True)
finally:
    epg.close()
lab = c.items[3].label
check('offline channel is greyed with the theme dim colour (%s)' % lab, colours(lab) == [t.dim])
playback.set_offline('104', False)

favs = playback.common.load_favs()
playback.common.toggle_fav('102')
w.load_channels('1', select_id='102')
star_lab = c.items[1].label
check('favourite channel is marked in bold (%s)' % star_lab,
      star_lab.startswith('[B]\u2022[/B] ') and '\u2605' not in star_lab)
playback.common.save_json('favourites.json', favs)   # put it back

# playing a channel from TV mode
c.sel = 1
w.onClick(200)
played = xbmc.Player.PLAYED[-1]
check('OK on a channel plays it (%s)' % played[1], played[1] == '2  Movie Box' and '/live/' in played[0])
check('the playing row is marked', c.items[c.sel].props.get('playing') == 'true')
w.onClick(200)
check('OK again goes fullscreen', xbmc.BUILTINS[-1] == 'ActivateWindow(fullscreenvideo)')

# number entry
w.onAction(xbmcgui.Action(61))            # digit 3
check('typed number shows the channel', w._props['digits'] == '3' and 'Sport HD' in w._props['digits_name'])
w.onAction(xbmcgui.Action(92))            # Back cancels it
check('Back cancels the number', w._props['digits'] == '' and not w.closed)
w.onAction(xbmcgui.Action(92))
check('Back again closes TV mode', w.closed)

# --------------------------------------------------------- grid guide
gwin = guide.GuideWindow(theme.GUIDE_XML, ADDON, theme.skin_dir(), '1080i')
gwin.setup('1', '101')
gwin.onInit()
check('grid guide opened with the group (%s)' % gwin._props['header'],
      'News' in gwin._props['header'] and len(gwin.rows) == 2)
check('guide built programme blocks', len(gwin.buttons) >= 2 * len(gwin.rows))
now_blocks = [b for r in gwin.cells for b, p in r if p['start'] <= time.time() < p['stop']]
check('blocks airing now use the theme text colour (%s)'
      % (now_blocks[0].kw['textColor'] if now_blocks else None),
      bool(now_blocks) and all(b.kw['textColor'] == t.text for b in now_blocks))
past = [b for r in gwin.cells for b, p in r if p['stop'] <= time.time()]
check('past programmes are dimmed', all(b.kw['textColor'] in (t.dim, t.catchup) for b in past))
check('focused block text is readable', gwin.buttons[0].kw['focusedColor'] == t.text_sel)
check('guide ticker only redraws when now leaves the window',
      not guide.now_wrapped(gwin.start, gwin.start + 60)
      and guide.now_wrapped(gwin.start, gwin.start + guide.SPAN))
check('a window scrolled into the past stays there',
      guide.now_wrapped(gwin.start, gwin.start + guide.SPAN + 1, gwin.start + guide.SPAN - 1)
      and not guide.now_wrapped(gwin.start, gwin.start + guide.SPAN + 20, gwin.start + guide.SPAN + 10))
check('grid redraws are throttled', guide.MIN_REDRAW >= 10)
gwin.close()

# ----------------------------------------------------------- the banner
data = overlay.banner_data(live_rows(Catalog(playback.common.catalog_path()), '1')[0])
check('banner has a logo, name and now/next: %s' % data['name'],
      data['logo'].startswith('http://x/') and data['name'] == 'News One' and data['now'])
check('banner has no colour markup (the layout colours it)', not colours(str(data)))

ov = overlay._Overlay(theme.BANNER_XML, ADDON, theme.skin_dir(), '1080i')
ov.bar = 0.4
ov.show()
check('banner comes from the STBEmu folder', overlay.theme.skin_dir() == 'stbemu')
check('banner progress bar width set', ov.getControl(10).width == int(overlay.BAR_WIDTH * 0.4))
ov.close()

# the keymap path is untouched by the skin: Up goes to the next channel in the group
sys.argv = ['plugin://plugin.video.xtreamcodes/', '1', '?action=zap&key=up']
from resources.lib import zapper   # noqa: E402
banner_rows = []
overlay.show_banner = lambda row, extra='', during=None: (
    banner_rows.append((row['name'], extra)), during and during())
xbmc.Player.FILE = played[0]
playback.remember_zap('*', '102')   # ...and Movie Box is the channel playing now
xbmc.Player.PLAYED.clear()          # forget the tuning done from TV mode above
zapper.handle('up')
check('Up during a channel shows a banner and tunes the next one (%s)' % (banner_rows,),
      banner_rows and banner_rows[-1][0] == 'Sport HD' and xbmc.Player.PLAYED[-1][1] == '3  Sport HD')
check('all colours used are the theme\'s',
      all(c in theme.STBEMU.__dict__.values() for c in (t.accent, t.dim, t.text)))

srv.shutdown()
sys.exit(1 if fails else 0)
