import os, sys, tempfile, time, json
ADDON='/home/claude/plugin.video.xtreamcodes'
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=['/home/claude/test/stubs', ADDON]
import fake_server_live as fake_server, xbmcaddon, xbmcgui, xbmc
fake_server.LIVE[:] = [{"num":i+1,"name":"Channel %d"%(i+1),"stream_id":5000+i,"stream_icon":"","epg_channel_id":"ch%d"%i,"category_id":"1","tv_archive":0} for i in range(30)]
fake_server.LIVE_CATS[:]=[{"category_id":"1","category_name":"G"}]
srv=fake_server.start(); S=xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='false', hide_adult='true', tv_autoplay='false')
from resources.lib import sync, tvwindow, guide, common, playback
sync.run_sync('full')
common.save_json('favourites.json', ['5001','5003'])
w=tvwindow.TVWindow('x',ADDON,'default','1080i'); w.cat_id='1'; w.onInit(); c=w.getControl(200)
print('TV mode:', [c.items[i].label for i in range(5)])
w.cat_id='*'; w.load_channels('1'); idx=w.index['5002']; c.selectItem(w._idx_to_pos(idx))
xbmcgui.Dialog.contextmenu=lambda self,o: 0
w._channel_menu(); print('after adding Channel 3 via menu ->', c.items[w._idx_to_pos(idx)].label)
w.close()
g=guide.GuideWindow('x',ADDON,'default','1080i'); g.setup('*',None); g.onInit()
print('grid names:', [g.getControl(guide.NAME+r).label for r in range(4)])
now=time.time()
# grid menu: add/remove favourite
xbmcgui.Dialog.contextmenu=lambda self,o: (print('menu:',o) or len(o)-1)
p={'start':now-60,'stop':now+600,'title':'x','noinfo':True}; g._menu(0,p)
print('favourites now:', common.load_favs()); g.close()
