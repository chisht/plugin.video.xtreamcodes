import os, sys, tempfile, runpy, json
ADDON=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=[os.path.join(ADDON,'tests','stubs'), os.path.join(ADDON,'tests'), ADDON]
import fake_server_live as fake_server, xbmcaddon, xbmcplugin, xbmcgui, xbmc
srv=fake_server.start()
S=xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='false', page_size='0', show_counts='false', hide_adult='true',
         check_stream='true', check_timeout='3', offline_zap='0', mark_offline='true', tv_stop_on_exit='true', tv_autoplay='false', live_format='0')
def run(q):
    xbmcplugin.ITEMS.clear(); xbmcplugin.RESOLVED.clear(); xbmc.BUILTINS.clear(); xbmcgui.DIALOGS.clear()
    sys.argv=['plugin://plugin.video.xtreamcodes/','1',q]; runpy.run_path(ADDON+'/main.py', run_name='__main__')
    return [li.label for u,li,f in xbmcplugin.ITEMS]
P=xbmc.Player
notes=lambda: [d[2] for d in xbmcgui.DIALOGS if d[0]=='notify']
print('channels:', run('?action=live_list&cat=*'))
print('channel item playable?', xbmcplugin.ITEMS[0][1].props.get('IsPlayable'))
run('?action=play_live&id=101&cat=*'); print('online 101 ->', P.PLAYED[-1][1], '| resolved via Kodi:', xbmcplugin.RESOLVED, '| busy spinner:', xbmc.BUILTINS)
n=len(P.PLAYED); run('?action=play_live&id=102&cat=*'); print('dead 102 -> played?', len(P.PLAYED)>n, '| notice:', notes(), '| resolved:', xbmcplugin.RESOLVED)
print('list shows offline:', run('?action=live_list&cat=*')[1])
# zap with skip: currently 101 playing; down from 101 goes... list order: 101,102,104,106,107,108,109 (103,105 adult hidden)
P.FILE = P.PLAYED[-1][0]; xbmcgui.PROPS['plugin.video.xtreamcodes.zap']=json.dumps({'cat':'*','id':'101'})
run('?action=zap&key=up'); print('zap up (skip mode) ->', P.PLAYED[-1][1], notes())
# 104 -> up: 106 is html error -> skip to 107
P.FILE=P.PLAYED[-1][0]; run('?action=zap&key=up'); print('zap up past HTML-error 106 ->', P.PLAYED[-1][1], notes())
# stay mode
S['offline_zap']='1'; xbmcgui.PROPS['plugin.video.xtreamcodes.offline']='{}'
xbmcgui.PROPS['plugin.video.xtreamcodes.zap']=json.dumps({'cat':'*','id':'101'}); P.FILE='%s/live/u/p%%40ss/101.ts'%('http://127.0.0.1:%d'%srv.server_address[1])
n=len(P.PLAYED); run('?action=zap&key=up'); print('stay mode, 102 dead -> played?', len(P.PLAYED)>n, notes(), json.loads(xbmcgui.PROPS['plugin.video.xtreamcodes.zap']))
run('?action=zap&key=up'); print('next press continues past it ->', P.PLAYED[-1][1])
# check disabled -> no probe, plays directly even if dead
S['check_stream']='false'; run('?action=play_live&id=102&cat=*'); print('check off, 102 ->', P.PLAYED[-1][1], 'spinner:', xbmc.BUILTINS); S['check_stream']='true'
# catch-up via guide item is not resolve-based
run('?action=play_catchup&id=101&start=2026-11-25 10:00:00&dur=60&title=Show'); print('catch-up ->', P.PLAYED[-1][0].split('|')[0][-40:], P.PLAYED[-1][1])
# TV mode: dead channel greyed, stop on exit
from resources.lib import tvwindow
P.FILE=''; xbmcgui.PROPS.pop('plugin.video.xtreamcodes.offline',None)
w=tvwindow.TVWindow('x',ADDON,'default','1080i'); w.onInit(); c=w.getControl(200)
c.sel=1; w.onClick(200); print('TV OK on dead 102:', repr(c.items[1].label), repr(c.items[1].l2), notes()[-1], 'playing:', w.playing_id)
c.sel=0; w.onClick(200); print('TV OK on 101 -> windowed', P.PLAYED[-1][2], 'playing', w.playing_id)
w.onAction(xbmcgui.Action(92)); print('closed, stopped:', getattr(P,'STOPPED',False), 'file now', repr(P.FILE))
S['tv_stop_on_exit']='false'; P.STOPPED=False
w=tvwindow.TVWindow('x',ADDON,'default','1080i'); w.onInit(); w.getControl(200).sel=0; w.onClick(200); w.onAction(xbmcgui.Action(92)); print('stop-on-exit off -> still playing:', bool(P.FILE), 'stopped', P.STOPPED)
