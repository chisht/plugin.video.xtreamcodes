import os, sys, tempfile, time, json, cProfile, pstats
ADDON=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=[os.path.join(ADDON,'tests','stubs'), os.path.join(ADDON,'tests'), ADDON]
import fake_server_live as fake_server, xbmcaddon, xbmcgui, xbmc
N=40187
fake_server.LIVE[:] = [{"num":i+1,"name":"Channel %d"%(i+1),"stream_id":5000+i,"stream_icon":"","epg_channel_id":"ch%d"%(i%300),"category_id":str(1+i%1700),"tv_archive":0} for i in range(N)]
fake_server.LIVE_CATS[:]=[{"category_id":str(i),"category_name":"Group %d"%i} for i in range(1,1701)]
srv=fake_server.start(); S=xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='false', hide_adult='true', tv_autoplay='false', show_counts='true')
from resources.lib import sync, tvwindow, common
sync.run_sync('full')
for i in range(3):
    w=tvwindow.TVWindow('x',ADDON,'default','1080i'); w.cat_id='5'
    pr=cProfile.Profile(); pr.enable(); w.onInit(); pr.disable(); w.close()
pstats.Stats(pr).sort_stats('cumtime').print_stats(15)
