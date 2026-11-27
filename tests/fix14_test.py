import os, sys, tempfile, time
ADDON='/home/claude/plugin.video.xtreamcodes'
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=['/home/claude/test/stubs', ADDON]
import fake_server_live as fake_server, xbmcaddon, xbmcgui, xbmc
fake_server.LIVE[:] = [{"num":i+1,"name":"Channel %d"%(i+1),"stream_id":5000+i,"stream_icon":"","epg_channel_id":"ch%d"%i,"category_id":"1","tv_archive":0} for i in range(21)]
fake_server.LIVE_CATS[:]=[{"category_id":"1","category_name":"G"}]
srv=fake_server.start(); S=xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='false', hide_adult='true')
from resources.lib import sync, guide
sync.run_sync('full')
g=guide.GuideWindow('x',ADDON,'default','1080i'); g.setup('*',None); g.onInit()
def cur():
    f=g.getFocusId(); r,i=g.by_id[f]; return g.offset, r, g.rows[g.offset+r]['name']
def press(a, n=1):
    for _ in range(n): g.onAction(xbmcgui.Action(a))
D,U=guide.ACTION_DOWN,guide.ACTION_UP
print('start', cur()); press(D,7); print('row 8 (last line)', cur())
press(D); print('down past last line ->', cur(), '(page, cursor on top)')
press(D,7); print('bottom of page 2', cur()); press(D); print('down again (21 rows: partial last page) ->', cur())
press(D,20); print('end of list stays', cur())
press(U,30); print('top of list', cur()); 
press(D,8); press(U); print('up past first line of page 2 ->', cur(), '(cursor on last line of page 1)')
