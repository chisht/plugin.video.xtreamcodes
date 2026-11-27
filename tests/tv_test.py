import os, sys, runpy, tempfile, time, json
ADDON=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
ud=tempfile.mkdtemp()
sys.path[:0]=[os.path.join(ADDON,'tests','stubs'), os.path.join(ADDON,'tests'), ADDON]
import xbmcvfs; xbmcvfs.translatePath=lambda p: p.replace('special://userdata', ud)
import fake_server, xbmcaddon, xbmcplugin, xbmcgui, xbmc
srv=fake_server.start()
xbmcaddon.SETTINGS.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='true', hide_adult='true', epg_past_days='2', live_format='0', zap_enable='true', show_counts='true', page_size='0', show_epg_in_list='true', catchup_pad='5')
from resources.lib import sync, keymap
sync.run_sync('full')
print('keymap changed:', keymap.apply()); print(open(keymap._path()).read()[:500])
def run(q):
    xbmcplugin.ITEMS.clear(); xbmcplugin.RESOLVED.clear(); xbmcgui.DIALOGS.clear(); xbmc.BUILTINS.clear()
    sys.argv=['plugin://plugin.video.xtreamcodes/','1',q]; runpy.run_path(ADDON+'/main.py', run_name='__main__')
# zap when nothing playing -> fallback
run('?action=zap&key=up'); print('fallback:', xbmc.BUILTINS)
# start channel from list in group 1, then zap
run('?action=play_live&id=101&cat=1'); xbmc.Player.FILE = xbmc.Player.PLAYED[-1][0]
run('?action=zap&key=up'); print('zap up ->', xbmc.Player.PLAYED[-1], xbmcgui.DIALOGS)
run('?action=zap&key=up'); print('zap up (wrap) ->', xbmc.Player.PLAYED[-1][1])
xbmcaddon.SETTINGS['zap_reverse']='true'; run('?action=zap&key=up'); print('reversed up ->', xbmc.Player.PLAYED[-1][1]); xbmcaddon.SETTINGS['zap_reverse']='false'
# catchup playing -> fallback
xbmc.Player.FILE='http://127.0.0.1/timeshift/x'; run('?action=zap&key=down'); print('during catchup:', xbmc.BUILTINS)
# TV window
xbmc.Player.FILE=''; xbmc.Player.PLAYED.clear()
from resources.lib import tvwindow
w = tvwindow.TVWindow('script-xtreamcodes-tv.xml', ADDON, 'default', '1080i'); w.onInit()
g=w.getControl(100); c=w.getControl(200); s=w.getControl(500)
print('groups:', [i.label for i in g.items]); print('channels:', [(i.label, i.l2) for i in c.items]); time.sleep(0.6)
print('info:', {k:w._props[k] for k in ('ch_name','now_line','has_now')}, 'bar width', w.getControl(406).width)
print('schedule:', [(i.label, i.l2) for i in s.items[:3]], '... sel', s.sel, s.items[s.sel].label)
w.onClick(200); print('OK #1 ->', xbmc.Player.PLAYED[-1], 'playing mark:', [i.props.get('playing') for i in c.items])
w.onClick(200); print('OK #2 ->', xbmc.BUILTINS[-1])
s.sel = 0; w.onClick(500); print('catch-up from schedule ->', xbmc.Player.PLAYED[-1][0][:110], xbmc.Player.PLAYED[-1][2])
# simulate zap in fullscreen to channel 102 -> worker syncs selection
c.sel=0; w.onClick(200); xbmc.Player.FILE = xbmc.Player.PLAYED[-1][0]
xbmcgui.PROPS['plugin.video.xtreamcodes.zap']=json.dumps({'cat':'*','id':'102'}); time.sleep(0.6)
print('after fullscreen zap: selected', c.sel, 'playing id', w.playing_id)
g.sel=2; w.onClick(100); print('group Sports ->', [i.label for i in c.items], w._props['header'])
w.onAction(xbmcgui.Action(92)); print('closed:', w.closed); time.sleep(0.4); print('thread alive:', w._thread.is_alive())
xbmcaddon.SETTINGS['zap_enable']='false'; print('keymap removed:', keymap.apply(), os.path.exists(keymap._path()))
print('errors:', [l for l in xbmc.LOG if 'stop' in l.lower() or 'fail' in l.lower()])
