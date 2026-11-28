import os, sys, tempfile, json, runpy, time
ADDON=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=[os.path.join(ADDON,'tests','stubs'), os.path.join(ADDON,'tests'), ADDON]
import fake_server_live as fake_server, xbmcaddon, xbmcgui, xbmc
fake_server.DEAD.clear(); fake_server.HTMLERR.clear()
P=xbmc.Player
# 1-connection plan: refuse a stream while a *different* stream of ours is playing
orig=fake_server.H.do_GET
def limited(self):
    if self.path.startswith('/live/'):
        sid=self.path.rsplit('/',1)[1].split('.')[0]
        if P.FILE and '/live/' in P.FILE and ('/%s.' % sid) not in P.FILE:
            self.send_response(403); self.end_headers(); return
    return orig(self)
fake_server.H.do_GET=limited
srv=fake_server.start(); S=xbmcaddon.SETTINGS; base='http://127.0.0.1:%d'%srv.server_address[1]
S.update(server=base, username='u', password='p@ss', epg_enable='false', hide_adult='true', check_stream='true', check_timeout='3', live_format='0', zap_enable='true', offline_zap='0', mark_offline='true')
from resources.lib import sync, playback
sync.run_sync('full')
def run(q):
    xbmc.BUILTINS.clear(); xbmcgui.DIALOGS.clear(); sys.argv=['plugin://plugin.video.xtreamcodes/','1',q]; runpy.run_path(ADDON+'/main.py', run_name='__main__')
notes=lambda: [d[2] for d in xbmcgui.DIALOGS if d[0]=='notify']
run('?action=play_live&id=101&cat=*'); P.FILE=P.PLAYED[-1][0]
S['switch_stop_first']='false'; P.STOPPED=False; P.FILE=P.PLAYED[-1][0]
run('?action=zap&key=up'); print('OLD (setting off): up ->', P.PLAYED[-1][1], '| old stream closed:', P.STOPPED, '| notices:', notes(), '| wrongly marked offline:', playback.is_offline('102'))
xbmcgui.PROPS.pop('plugin.video.xtreamcodes.offline', None); playback._OFFLINE_CACHE['t']=0
S['switch_stop_first']='true'; P.FILE=P.PLAYED[-1][0]
run('?action=zap&key=up'); print('NEW: up ->', P.PLAYED[-1][1], '| stopped first:', P.STOPPED, '| notices:', notes())
# stay mode with a genuinely dead channel: old channel resumes
fake_server.DEAD.add('106'); S['offline_zap']='1'; run('?action=play_live&id=102&cat=*'); P.FILE=P.PLAYED[-1][0]; cur=P.PLAYED[-1][1]
run('?action=zap&key=up'); print('stay mode, next is dead -> playing again:', P.PLAYED[-1][1], '(was %s)' % cur, '|', notes())
# TV mode switch (windowed) also frees the connection
from resources.lib import tvwindow
w=tvwindow.TVWindow('x',ADDON,'default','1080i'); w.onInit(); c=w.getControl(200); time.sleep(0.4)
P.STOPPED=False; c.sel=[r['name'] for r in w.rows].index('News One'); w.onClick(200); print('TV mode switch -> stopped first:', P.STOPPED, '| playing', P.PLAYED[-1][1], 'windowed', P.PLAYED[-1][2])
w.onAction(xbmcgui.Action(60)); print('typed 2 ->', w._props['digits_name']); w._clear_digits()
w.onAction(xbmcgui.Action(58)); print('typed 0 ->', w._props['digits_name']); w._clear_digits()
print('ui_open while TV mode open:', xbmcgui.PROPS.get('plugin.video.xtreamcodes.ui_open')); w.close(); print('after close:', xbmcgui.PROPS.get('plugin.video.xtreamcodes.ui_open'))
