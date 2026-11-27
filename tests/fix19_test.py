import os, sys, tempfile, time
ADDON=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=[os.path.join(ADDON,'tests','stubs'), os.path.join(ADDON,'tests'), ADDON]
import fake_server_live as fake_server, xbmcaddon, xbmcgui, xbmc
fake_server.LIVE[:] = [{"num":i+1,"name":"Channel %d"%(i+1),"stream_id":5000+i,"stream_icon":"","epg_channel_id":"c%d"%i,"category_id":"1","tv_archive":1,"tv_archive_duration":3} for i in range(5)]
fake_server.LIVE_CATS[:]=[{"category_id":"1","category_name":"G"}]
srv=fake_server.start(); S=xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='false', hide_adult='true', check_stream='false', tv_autoplay='false')
from resources.lib import sync, tvwindow, guide, playback
sync.run_sync('full'); P=xbmc.Player
asked=[]; xbmcgui.Dialog.contextmenu=lambda self,o:(asked.append(o) or 0)
now=time.time(); past={'start':now-7200,'stop':now-3600,'title':'Old show'}; airing={'start':now-60,'stop':now+600,'title':'Now show'}
# --- TV mode schedule
w=tvwindow.TVWindow('x',ADDON,'default','1080i'); w.onInit(); w._stop.set(); time.sleep(0.5); row=w.rows[0]
w.sched_row=row; w.sched=[past, airing]; sc=w.getControl(tvwindow.SCHEDULE); sc.items=[1,2]
def click(pos): sc.sel=pos; xbmc.BUILTINS.clear(); w.onClick(tvwindow.SCHEDULE); return list(xbmc.BUILTINS)
n=len(P.PLAYED); print('TV mode: OK on a recording ->', click(0), '| started:', len(P.PLAYED)-n)
print('TV mode: OK on the same recording again ->', click(0), '| started again:', len(P.PLAYED)-n-1)
P.FILE=''; w._prog_key=None
print('TV mode: OK on the airing programme (archive channel) -> popup:', asked, '| live started:', (click(1), '/live/' in P.PLAYED[-1][0])[1])
w.close()
# --- grid
g=guide.GuideWindow('x',ADDON,'default','1080i'); g.setup('*',None); g.onInit(); playback.UI['win']=g
xbmc.BUILTINS.clear(); g._select(0,past); print('grid: recording started in mini player:', P.PLAYED[-1][2])
g._select(0,past); print('grid: OK again ->', xbmc.BUILTINS)
xbmc.BUILTINS.clear(); asked.clear(); xbmcgui.Dialog.contextmenu=lambda self,o:(asked.append(o) or len(o)-1); g._menu(0,airing)
print('grid menu:', asked[0], '->', xbmc.BUILTINS)
