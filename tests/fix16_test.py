import os, sys, tempfile, time
ADDON='/home/claude/plugin.video.xtreamcodes'
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=['/home/claude/test/stubs', ADDON]
import fake_server_live as fake_server, xbmcaddon, xbmcgui, xbmc
fake_server.LIVE[:] = [{"num":i+1,"name":"Channel %d"%(i+1),"stream_id":5000+i,"stream_icon":"","epg_channel_id":"ch%d"%i,"category_id":"1","tv_archive":1,"tv_archive_duration":3} for i in range(10)]
fake_server.LIVE_CATS[:]=[{"category_id":"1","category_name":"G"}]
srv=fake_server.start(); S=xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='false', hide_adult='true')
from resources.lib import sync, guide
sync.run_sync('full'); P=xbmc.Player
g=guide.GuideWindow('x',ADDON,'default','1080i'); g.setup('*',None); g.onInit()
asked=[]; xbmcgui.Dialog.contextmenu=lambda self,o: (asked.append(o) or 0)
now=time.time(); p={'start':now-60,'stop':now+600,'title':'x'}
print('archive channel:', g.rows[0]['archive'], '| airing programme OK ->'); g._select(0,p)
print('  played:', P.PLAYED[-1][1], '/ live url:', '/live/' in P.PLAYED[-1][0], '| questions asked:', asked)
asked.clear(); g._menu(0,p); print('context menu offers:', asked[0])
