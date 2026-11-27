import os, sys, tempfile, sqlite3, runpy
ADDON=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=[os.path.join(ADDON,'tests','stubs'), os.path.join(ADDON,'tests'), ADDON]
import fake_server_adult as fake_server, xbmcaddon, xbmcplugin, xbmcgui, xbmc
srv=fake_server.start()
xbmcaddon.SETTINGS.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='false', page_size='0', show_counts='true', hide_adult='true')
# simulate an old v1.2 catalog file -> must be rebuilt
con=sqlite3.connect(prof+'/catalog.db'); con.execute('CREATE TABLE meta(key TEXT, value TEXT)'); con.commit(); con.close()
def run(q):
    xbmcplugin.ITEMS.clear(); xbmcplugin.RESOLVED.clear(); sys.argv=['plugin://plugin.video.xtreamcodes/','1',q]; runpy.run_path(ADDON+'/main.py', run_name='__main__'); return [li.label for u,li,f in xbmcplugin.ITEMS]
print('HIDE live groups :', run('?action=live_cats'))
print('HIDE all channels:', run('?action=live_list&cat=*'))
print('HIDE movies      :', run('?action=vod_list&cat=*'), run('?action=vod_cats'))
xbmcgui.Dialog.INPUT='xxx'; print('HIDE search xxx  :', run('?action=search'))
from resources.lib.common import save_json; save_json('favourites.json', ['103','101'])
print('HIDE favourites  :', run('?action=live_list&cat=fav'))
from resources.lib import tvwindow
w=tvwindow.TVWindow('x',ADDON,'default','1080i'); w.onInit(); w._focus=200
print('HIDE TV groups   :', [i.label for i in w.getControl(100).items])
w.onAction(xbmcgui.Action(61)); print('HIDE typed 3     :', w._props['digits_name']); w.close()
xbmcaddon.SETTINGS['hide_adult']='false'
print('SHOW live groups :', run('?action=live_cats'))
print('SHOW all channels:', run('?action=live_list&cat=*'))
print('SHOW movies      :', run('?action=vod_list&cat=*'))
