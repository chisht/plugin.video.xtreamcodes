import os, sys, tempfile, runpy, threading, time
ADDON='/home/claude/plugin.video.xtreamcodes'
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=['/home/claude/test/stubs', ADDON]
import fake_server_live as fake_server, xbmcaddon, xbmcgui, xbmc, xbmcplugin
fake_server.LIVE[:] = [{"num":i+1,"name":"Channel %d"%(i+1),"stream_id":5000+i,"stream_icon":"","epg_channel_id":"c%d"%i,"category_id":"1","tv_archive":0} for i in range(12)]
fake_server.LIVE_CATS[:]=[{"category_id":"1","category_name":"G"}]
srv=fake_server.start(); S=xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='false', hide_adult='true', page_size='0', check_stream='false', zap_reverse='false', zap_debounce='3')
from resources.lib import sync, playback, overlay
sync.run_sync('full'); P=xbmc.Player
banners=[]; overlay._hold=lambda win,seq,secs: time.sleep(0.9)
class FakeWin:
    def show(self): pass
    def setProperty(self,*a): pass
overlay._Overlay=lambda *a,**k: FakeWin()
orig=overlay.show_banner
def show(row,extra='',during=None): banners.append(row['name']); return orig(row,extra,during)
overlay.show_banner=show
def run(q):
    sys.argv=['plugin://plugin.video.xtreamcodes/','1',q]; runpy.run_path(ADDON+'/main.py', run_name='__main__')
rows=None
run('?action=live&cat=1') if False else None
# start on channel 1
from resources.lib.catalog import Catalog, live_rows
c=Catalog(playback.common.catalog_path()); rows=live_rows(c,'1'); c.close()
path,li=playback.live_item(rows[0]); playback.remember_zap('1',rows[0]['stream_id'],row=rows[0]); P().play(path,li)
n=len(P.PLAYED)
print('first press (not a burst) tunes at once ->', (run('?action=zap&key=up'), len(P.PLAYED)-n, P.PLAYED[-1][1])[1:])
n=len(P.PLAYED); banners.clear()
ts=[]
for i in range(4):
    t=threading.Thread(target=run,args=('?action=zap&key=up',)); t.start(); ts.append(t); time.sleep(0.15)
for t in ts: t.join()
print('4 quick presses: banners', banners, '| channels tuned:', len(P.PLAYED)-n, '->', P.PLAYED[-1][1])
S['zap_debounce']='0'; n=len(P.PLAYED)
run('?action=zap&key=up'); run('?action=zap&key=up'); print('debounce off: tuned', len(P.PLAYED)-n, 'times')
