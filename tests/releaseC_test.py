import os, sys, tempfile, json, runpy, time
ADDON=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=[os.path.join(ADDON,'tests','stubs'), os.path.join(ADDON,'tests'), ADDON]
import fake_server_groups as fake_server, xbmcaddon, xbmcgui, xbmc, xbmcplugin
srv=fake_server.start(); S=xbmcaddon.SETTINGS; base='http://127.0.0.1:%d'%srv.server_address[1]
S.update(server=base, username='u', password='p@ss', epg_enable='false', hide_adult='true', page_size='0', show_counts='false', check_stream='false', tv_autoplay='false')
from resources.lib import sync, common, customize
sync.run_sync('full')
def run(q):
    xbmc.BUILTINS.clear(); xbmcgui.DIALOGS.clear(); xbmcplugin.ITEMS.clear(); sys.argv=['plugin://plugin.video.xtreamcodes/','1',q]; runpy.run_path(ADDON+'/main.py', run_name='__main__')
    return [li.label for u,li,f in xbmcplugin.ITEMS]
grp=lambda: [l for l in run('?action=live_cats')[2:-1]]
print('groups:', grp(), '| context:', [c[0] for c in xbmcplugin.ITEMS[2][1].ctx])
# rename "|FR| Sport" -> "French sport"; then empty resets
orig=xbmcgui.Dialog.input; xbmcgui.Dialog.ANSWERS=['French sport']; xbmcgui.Dialog.input=lambda self,*a,**k: xbmcgui.Dialog.ANSWERS.pop(0)
run('?action=rename_group&kind=live&id=6'); print('renamed:', grp())
# move "US: Locals" (7) to the top
xbmcgui.Dialog.ANSWERS=[0]; xbmcgui.Dialog.select=lambda self,h,opts,**k: (xbmcgui.DIALOGS.append(('select',h,opts)), xbmcgui.Dialog.ANSWERS.pop(0))[1]
run('?action=move_group&kind=live&id=7'); print('US to top:', grp())
# move "News" (1) above "French sport"
groups_now=grp(); xbmcgui.Dialog.ANSWERS=[1+[g for g in groups_now if g!='News'].index('French sport')]; run('?action=move_group&kind=live&id=1'); print('News above French sport:', grp())
# channel order in All channels: move "AR News" (109) to the top
print('all before:', run('?action=live_list&cat=*')); xbmcgui.Dialog.ANSWERS=[0]; run('?action=move_channel&id=109&cat=*'); print('all after :', run('?action=live_list&cat=*'))
# TV mode reflects names/order
from resources.lib import tvwindow
w=tvwindow.TVWindow('x',ADDON,'default','1080i'); w.onInit(); print('TV groups:', [i.label for i in w.getControl(100).items]); print('TV all channels:', [i.label for i in w.getControl(200).items][:3]); w.close()
# favourites order
common.save_json('favourites.json',['101','106','107']); xbmcgui.Dialog.ANSWERS=[0]; run('?action=move_channel&id=107&cat=fav'); print('fav order:', common.load_favs())
# PIN
S['adult_pin']='1234'; r=run('?'); print('root offers:', [l for l in r if 'adult' in l])
xbmcgui.Dialog.NUMERIC='9999'; run('?action=adult_unlock'); print('wrong PIN:', [d[2] for d in xbmcgui.DIALOGS if d[0]=='notify'], '| adult group visible:', any('ADULT' in g for g in grp()))
xbmcgui.Dialog.NUMERIC='1234'; run('?action=adult_unlock'); print('right PIN:', [d[2] for d in xbmcgui.DIALOGS if d[0]=='notify'], '| adult group visible:', [g for g in grp() if 'ADULT' in g])
print('root now offers:', [l for l in run('?') if 'adult' in l.lower()])
run('?action=adult_lock'); print('locked again, adult visible:', any('ADULT' in g for g in grp()))
# backup & restore
bdir=tempfile.mkdtemp(); xbmcgui.Dialog.BROWSE=bdir
open(os.path.join(prof,'settings.xml'),'w').write('<settings version="2"><setting id="server">%s</setting><setting id="hide_adult">true</setting><setting id="page_size">300</setting></settings>' % base)
run('?action=backup_create'); f=os.listdir(bdir)[0]; data=json.load(open(os.path.join(bdir,f))); print('backup file:', f[:22], '| has:', sorted(data['files']), '| settings:', sorted(data['settings']))
common.save_json('favourites.json', []); customize.reset(); S['page_size']='0'
xbmcgui.Dialog.BROWSE=os.path.join(bdir,f); xbmcgui.Dialog.ANSWERS=[True]; run('?action=backup_restore')
print('restored favs:', common.load_favs(), '| page_size:', S['page_size'], '| groups:', grp()[:2])
xbmcgui.Dialog.ANSWERS=[True]; run('?action=reset_custom'); print('after reset:', grp()[:3])
