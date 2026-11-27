import os, sys, tempfile, time, json, runpy
ADDON='/home/claude/plugin.video.xtreamcodes'
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=['/home/claude/test/stubs', ADDON]
import fake_server, xbmcaddon, xbmcplugin, xbmcgui, xbmc
srv=fake_server.start()
xbmcaddon.SETTINGS.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='true', hide_adult='true', epg_past_days='1', live_format='0', show_counts='true', page_size='0', show_epg_in_list='true', tv_autoplay='true')
from resources.lib import sync, tvwindow, common
sync.run_sync('full')
def win():
    w = tvwindow.TVWindow('x.xml', ADDON, 'default', '1080i'); w.onInit(); return w
w = win(); g=w.getControl(100); c=w.getControl(200)
print('groups:', [i.label for i in g.items]); print('autoplay with no history:', xbmc.Player.PLAYED)
# context menu: add News One to favourites
w._focus = 200; c.sel = 0; xbmcgui.Dialog.CTX = 0; w.onAction(xbmcgui.Action(117))
print('menu:', [d for d in xbmcgui.DIALOGS if d[0]=='ctx'][-1], '-> favs', common.load_favs(), '| groups now:', g.items[1].label)
g.sel = 1; w.onClick(100); print('Favourites group:', [i.label for i in c.items])
# number entry: type 2 -> Sport Max
w.onAction(xbmcgui.Action(60)); print('typed:', w._props['digits'], w._props['digits_name']); time.sleep(2.3)
print('after timeout ->', xbmc.Player.PLAYED[-1][1], 'windowed', xbmc.Player.PLAYED[-1][2], '| group switched to', w.cat_id, '| selected', c.items[c.sel].label, '| overlay', repr(w._props['digits']))
# typed number that does not exist, then Back cancels
w.onAction(xbmcgui.Action(66)); print('typed 8:', w._props['digits_name']); w.onAction(xbmcgui.Action(92)); print('back cancels digits, window open:', not w.closed, repr(w._props['digits']))
w.onAction(xbmcgui.Action(92)); print('back again closes:', w.closed)
# reopen after restart: nothing playing -> resumes last channel
xbmc.Player.FILE=''; xbmc.Player.PLAYED.clear(); xbmcgui.PROPS.clear()
w2 = win(); print('reopen autoplay ->', xbmc.Player.PLAYED, 'group', w2.cat_id, 'selected', w2.getControl(200).items[w2.getControl(200).sel].label); w2.close()
# a movie is playing -> don't interrupt
xbmc.Player.FILE='http://x/movie/u/p/555.mkv'; xbmc.Player.PLAYED.clear(); xbmcgui.PROPS.clear()
w3 = win(); print('movie playing, autoplay skipped:', xbmc.Player.PLAYED == []); w3.close()
# list mode favourites + zap within favourites
def run(q):
    xbmcplugin.ITEMS.clear(); xbmcplugin.RESOLVED.clear(); xbmc.BUILTINS.clear(); sys.argv=['plugin://plugin.video.xtreamcodes/','1',q]; runpy.run_path(ADDON+'/main.py', run_name='__main__')
run('?action=live_cats'); print('live cats:', [li.label for u,li,f in xbmcplugin.ITEMS][:2])
run('?action=fav_toggle&id=102'); print('favs:', common.load_favs(), xbmc.BUILTINS)
run('?action=live_list&cat=fav'); print('fav list:', [li.label for u,li,f in xbmcplugin.ITEMS], [x[0] for x in xbmcplugin.ITEMS[0][1].ctx])
run('?action=play_live&id=101&cat=fav'); xbmc.Player.FILE = xbmc.Player.PLAYED[-1][0]
run('?action=zap&key=down'); print('zap in favourites ->', xbmc.Player.PLAYED[-1][1])
print('log errors:', [l for l in xbmc.LOG if 'stop' in l.lower() or 'fail' in l.lower()])
