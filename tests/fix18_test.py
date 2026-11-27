import os, sys, tempfile, runpy, time
ADDON=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=[os.path.join(ADDON,'tests','stubs'), os.path.join(ADDON,'tests'), ADDON]
import fake_server_live as fake_server, xbmcaddon, xbmcgui, xbmc, xbmcplugin
fake_server.LIVE[:] = [{"num":i+1,"name":"Channel %d"%(i+1),"stream_id":5000+i,"stream_icon":"","epg_channel_id":"c%d"%i,"category_id":"1","tv_archive":0} for i in range(12)]
fake_server.LIVE_CATS[:]=[{"category_id":"1","category_name":"G"}]
srv=fake_server.start(); S=xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='false', hide_adult='true', page_size='0', check_stream='false', tv_autoplay='false')
from resources.lib import sync, playback, tvwindow, guide
sync.run_sync('full'); P=xbmc.Player
def run(q):
    xbmcgui.DIALOGS.clear(); sys.argv=['plugin://plugin.video.xtreamcodes/','1',q]; runpy.run_path(ADDON+'/main.py', run_name='__main__')
toasts=lambda: [d[2] for d in xbmcgui.DIALOGS if d[0]=='notify']
run('?action=play_live&id=5003&title=Channel+4'); print('list/search play ->', toasts())
run('?action=zap&key=up'); print('fullscreen Up (banner instead) ->', toasts())
w=tvwindow.TVWindow('x',ADDON,'default','1080i'); playback.UI['win']=w; w.onInit()
xbmcgui.DIALOGS.clear(); seen={}
orig=xbmc.Player.play
def spy(self,*a,**k): seen['note']=w.getProperty('tuning'); return orig(self,*a,**k)
xbmc.Player.play=spy
w.play_channel(w.rows[2]); print('TV mode -> note in window:', repr(seen['note']), '| toasts:', toasts())
time.sleep(3.2); print('   note cleared:', repr(w.getProperty('tuning'))); w.close(); playback.UI['win']=None
g=guide.GuideWindow('x',ADDON,'default','1080i'); g.setup('*',None); g.onInit(); playback.UI['win']=g
spy2=lambda self,*a,**k: (seen.__setitem__('note', g.getProperty('tuning')), orig(self,*a,**k))[1]; xbmc.Player.play=spy2
xbmcgui.DIALOGS.clear(); now=time.time(); g._select(0,{'start':now-60,'stop':now+600,'title':'x'})
print('grid -> note:', repr(seen['note']), '| toasts:', toasts()); time.sleep(3.2); print('   cleared:', repr(g.getProperty('tuning')))
