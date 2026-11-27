import os, sys, tempfile, runpy, json
ADDON=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=[os.path.join(ADDON,'tests','stubs'), os.path.join(ADDON,'tests'), ADDON]
import fake_server_live as fake_server, xbmcaddon, xbmcgui, xbmc, xbmcplugin
fake_server.LIVE[:] = [{"num":i+1,"name":("Alpha %d" if i%2 else "Beta %d")%(i+1),"stream_id":5000+i,"stream_icon":"","epg_channel_id":"c%d"%i,"category_id":str(1+i%2),"tv_archive":0} for i in range(12)]
fake_server.LIVE_CATS[:]=[{"category_id":"1","category_name":"Odd"},{"category_id":"2","category_name":"Even"}]
srv=fake_server.start(); S=xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='false', hide_adult='true', page_size='0', check_stream='false', zap_reverse='false')
from resources.lib import sync, playback, common
sync.run_sync('full'); P=xbmc.Player
def run(q):
    xbmcplugin.ITEMS.clear(); sys.argv=['plugin://plugin.video.xtreamcodes/','1',q]; runpy.run_path(ADDON+'/main.py', run_name='__main__')
run('?action=search&q=Alpha')
url=[u for u,li,f in xbmcplugin.ITEMS if 'Alpha 4' in li.label][0]; print('search result link:', url.split('?')[1])
run('?'+url.split('?')[1])
st=playback.zap_state(); print('playing', P.PLAYED[-1][1], '| zap group:', st['cat'], '(Alpha 4 is in group 2 "Even")')
names=[]
for _ in range(3):
    run('?action=zap&key=up'); names.append(P.PLAYED[-1][1])
print('Up x3 ->', names, '(all in the same group: even numbers)')
