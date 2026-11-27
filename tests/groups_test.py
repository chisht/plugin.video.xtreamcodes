import os, sys, tempfile, runpy
ADDON='/home/claude/plugin.video.xtreamcodes'
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=['/home/claude/test/stubs', ADDON]
import fake_server_groups as fake_server, xbmcaddon, xbmcplugin, xbmcgui, xbmc
srv=fake_server.start()
xbmcaddon.SETTINGS.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='false', page_size='0', show_counts='false', hide_adult='true')
def run(q):
    xbmcplugin.ITEMS.clear(); xbmc.BUILTINS.clear(); sys.argv=['plugin://plugin.video.xtreamcodes/','1',q]; runpy.run_path(ADDON+'/main.py', run_name='__main__'); return [li.label for u,li,f in xbmcplugin.ITEMS]
print('groups:', run('?action=live_cats'))
print('ctx on group:', [x[0] for x in xbmcplugin.ITEMS[2][1].ctx])
run('?action=hide_group&kind=live&id=6'); print('after hiding |FR|:', run('?action=live_cats')[2:], '| refresh:', xbmc.BUILTINS)
print('all channels w/o FR:', run('?action=live_list&cat=*'))
# keep only UK, US prefixes
xbmcgui.Dialog.ANSWERS=[1, 'uk, us', True]; run('?action=manage_groups&kind=live')
print('keep UK,US ->', run('?action=live_cats')[2:], [d for d in xbmcgui.DIALOGS if d[0]=='ask'][-1])
print('all channels:', run('?action=live_list&cat=*'))
xbmcgui.Dialog.INPUT='News'; print('search News:', run('?action=search'))
# hide by word
xbmcgui.Dialog.ANSWERS=[3]; run('?action=manage_groups&kind=live'); print('show all:', run('?action=live_cats')[2:])
xbmcgui.Dialog.ANSWERS=[2, 'arabic']; run('?action=manage_groups&kind=live'); print('hide ARABIC:', run('?action=live_cats')[2:])
# pick individually: settings button path (no kind) -> choose Live, then multiselect keep first two
xbmcgui.Dialog.ANSWERS=[0, 0, [0,1]]; run('?action=manage_groups'); print('picked 2:', run('?action=live_cats')[2:])
# TV mode group menu
xbmcgui.Dialog.ANSWERS=[3]
from resources.lib import tvwindow
w=tvwindow.TVWindow('x',ADDON,'default','1080i'); w.onInit(); w._focus=100
print('TV groups:', [i.label for i in w.getControl(100).items])
xbmcgui.Dialog.CTX=1; w.getControl(100).sel=2; w.onAction(xbmcgui.Action(117))   # 'Show/hide groups...' -> Live? kind given -> mode 3 show all
print('TV after show-all:', [i.label for i in w.getControl(100).items])
xbmcgui.Dialog.CTX=0; w.getControl(100).sel=2; w.onClick(100); w._focus=100; w.onAction(xbmcgui.Action(117))
print('TV after hiding current group:', [i.label for i in w.getControl(100).items], 'now showing', w.cat_id); w.close()
