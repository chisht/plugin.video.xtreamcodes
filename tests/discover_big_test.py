import os, sys, tempfile, time
ADDON='/home/claude/plugin.video.xtreamcodes'
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=['/home/claude/test/stubs', ADDON]
import fake_server_live as fs, xbmcaddon
fs.VOD_LIST[:]=[{"name":"EN - Some Movie Number %d (%d)"%(i,1950+i%75),"stream_id":10000+i,"container_extension":"mp4","category_id":"10"} for i in range(100000)]
srv=fs.start(); S=xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='false', hide_adult='true')
from resources.lib import sync, tmdb, catalog, common
sync.run_sync('full')
cat=catalog.Catalog(common.catalog_path())
titles=[{'id':str(i),'title':'Some Movie Number %d'%(i*997),'orig':'','year':str(1950+(i*997)%75)} for i in range(100)]
t=time.time(); m=tmdb.match(cat,'movie',titles); print('first match (builds the title index for 100,000 movies): %.1fs, matched %d/100'%(time.time()-t,len(m)))
t=time.time(); m=tmdb.match(cat,'movie',titles); print('later matches: %.2fs'%(time.time()-t))
