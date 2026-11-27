import os, sys, tempfile, runpy, json, time
ADDON='/home/claude/plugin.video.xtreamcodes'
os.environ['ADDON_DIR']=ADDON; prof=tempfile.mkdtemp(); os.environ['PROFILE_DIR']=prof
sys.path[:0]=['/home/claude/test/stubs', ADDON]
import fake_server_trakt_xc as fake_server, fake_trakt, xbmcaddon, xbmcplugin, xbmcgui, xbmc
srv=fake_server.start(); tsrv=fake_trakt.start(); S=xbmcaddon.SETTINGS
S.update(server='http://127.0.0.1:%d'%srv.server_address[1], username='u', password='p@ss', epg_enable='false', hide_adult='true', page_size='0',
         trakt_client_id='CID', trakt_client_secret='SECRET', trakt_scrobble='true', check_stream='false')
from resources.lib import trakt, sync, common
trakt.API = 'http://127.0.0.1:%d' % tsrv.server_address[1]
sync.run_sync('full')
def run(q):
    xbmcplugin.ITEMS.clear(); xbmc.BUILTINS.clear(); xbmcgui.DIALOGS.clear()
    sys.argv=['plugin://plugin.video.xtreamcodes/','1',q]; g=runpy.run_path(ADDON+'/main.py', run_name='__main__')
    g['trakt'].API = trakt.API
    return [(li.label, li.tag.d.get('playcount')) for u,li,f in xbmcplugin.ITEMS]
# runpy re-imports resources.lib.trakt from cache (same module object) so API patch holds
print('series menu before link:', [l for l,_ in run('?action=series_cats')][:2])
run('?action=trakt_link'); print('link dialogs:', [d[:3] for d in xbmcgui.DIALOGS])
print('token:', {k: v for k, v in trakt.token().items() if k in ('access_token','username')}, '| polls:', fake_trakt.STATE['polls'])
print('root:', [l for l,_ in run('?')][:6])
print('series menu:', [l for l,_ in run('?action=series_cats')][:3])
print('IN PROGRESS:', [l for l,_ in run('?action=trakt_shows&which=progress')])
print('WATCHED   :', [l for l,_ in run('?action=trakt_shows&which=watched')])
print('all series:', run('?action=series_list&cat=*'))
print('BB seasons:', run('?action=seasons&id=78'))
print('BB eps    :', run('?action=episodes&id=78&season=1'))
print('movies    :', run('?action=vod_list&cat=*'))
# scrobble Beach Show S1E2
items = {li.label: u for u,li,f in xbmcplugin.ITEMS} if run('?action=episodes&id=77&season=1') else {}
url = [u for u,li,f in xbmcplugin.ITEMS if li.label=='E2'][0]
run('?' + url.split('?',1)[1]); print('now playing prop:', xbmcgui.PROPS.get('plugin.video.xtreamcodes.trakt_now'))
xbmc.Player.FILE = xbmcplugin.RESOLVED[-1][1].path; xbmc.Player.TOTAL=1500; xbmc.Player.TIME=100
sc = trakt.Scrobbler(); sc.onAVStarted(); xbmc.Player.TIME=700; sc.onPlayBackPaused(); sc.onPlayBackResumed(); xbmc.Player.TIME=1400; sc.tick(); sc.onPlayBackStopped()
print('scrobbles:', [(p.rsplit('/',1)[1], b.get('progress'), b.get('show'), b.get('episode')) for m,p,b,a,k in fake_trakt.LOG if p.startswith('/scrobble/')])
print('IN PROGRESS after:', [l for l,_ in run('?action=trakt_shows&which=progress')])
print('WATCHED after   :', [l for l,_ in run('?action=trakt_shows&which=watched')])
# movie scrobble with title fallback (no tmdb): Inception
url = [u for u,li,f in xbmcplugin.ITEMS] if run('?action=vod_list&cat=*') else []
u = [u for u,li,f in xbmcplugin.ITEMS if 'Inception' in li.label][0]; run('?'+u.split('?',1)[1])
xbmc.Player.FILE = xbmcplugin.RESOLVED[-1][1].path; sc.onAVStarted(); sc.onPlayBackEnded()
print('movie scrobble body:', [b for m,p,b,a,k in fake_trakt.LOG if p=='/scrobble/stop'][-1])
# live channel playing -> no scrobble
n=len(fake_trakt.LOG); run('?action=play_live&id=101&cat=*'); xbmc.Player.FILE=xbmc.Player.PLAYED[-1][0]; sc.onAVStarted(); sc.onPlayBackStopped(); print('live TV scrobbled?', len(fake_trakt.LOG)>n)
# expired token -> refresh
tok=trakt.token(); tok['created_at']=0; common.save_json('trakt_token.json', tok)
trakt.sync_watched(); print('after refresh token:', trakt.token()['access_token'], '| every request had api key:', all(k=='CID' for m,p,b,a,k in fake_trakt.LOG))
# not linked -> lists hidden, ticks gone
xbmcgui.Dialog.ANSWERS=[True]; run('?action=trakt_unlink'); print('after unlink series menu:', [l for l,_ in run('?action=series_cats')][:2], '| movies:', run('?action=vod_list&cat=*')[:2])
