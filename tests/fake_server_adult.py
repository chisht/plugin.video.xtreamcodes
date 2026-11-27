import base64, gzip, json, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
SEEN_UA = []
def b64(s): return base64.b64encode(s.encode()).decode()
def tz_str(ts): return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))
NOW = int(time.time()) // 3600 * 3600
LIVE_EXTRA = [{"num":3,"name":"Hot XXX","stream_id":103,"stream_icon":"","epg_channel_id":"","category_id":"3","tv_archive":0},
              {"num":4,"name":"Cartoons","stream_id":104,"stream_icon":"","epg_channel_id":"","category_id":"4","tv_archive":0},
              {"num":5,"name":"Flagged","stream_id":105,"stream_icon":"","epg_channel_id":"","category_id":"1","is_adult":"1","tv_archive":0}]
LIVE = [{"num":1,"name":"News One","stream_id":101,"stream_icon":"http://x/n1.png","epg_channel_id":"News1.uk","category_id":"1","tv_archive":1,"tv_archive_duration":"3"},
        {"num":2,"name":"Sport \"Max\"","stream_id":102,"stream_icon":"","epg_channel_id":"sport.max","category_ids":[1,2],"category_id":"1","tv_archive":0,"tv_archive_duration":0}]
def xmltv():
    out=['<?xml version="1.0" encoding="UTF-8"?><tv>','<channel id="News1.uk"><display-name>News One</display-name></channel>']
    for ch in ("News1.uk","sport.max"):
        for h in range(-30, 30):
            s=NOW+h*3600; e=s+3600
            out.append('<programme start="%s +0000" stop="%s +0000" channel="%s"><title>%s show %d</title><desc>Desc &amp; more</desc></programme>' % (time.strftime('%Y%m%d%H%M%S',time.gmtime(s)),time.strftime('%Y%m%d%H%M%S',time.gmtime(e)),ch,ch,h))
    out.append('</tv>'); return '\n'.join(out).encode()
class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def send(self, body, gz=False, ctype='application/json'):
        if gz: body=gzip.compress(body)
        self.send_response(200); self.send_header('Content-Type',ctype)
        if gz: self.send_header('Content-Encoding','gzip')
        self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        SEEN_UA.append(self.headers.get('User-Agent'))
        u=urllib.parse.urlsplit(self.path); q=dict(urllib.parse.parse_qsl(u.query))
        if u.path=='/xmltv.php': return self.send(xmltv(), gz=True, ctype='application/xml')
        if q.get('password')!='p@ss': return self.send(json.dumps({"user_info":{"auth":0}}).encode())
        a=q.get('action')
        if not a: r={"user_info":{"username":"u","auth":1,"status":"Active","exp_date":"1900000000","active_cons":"0","max_connections":"2","allowed_output_formats":["ts","m3u8"]},"server_info":{"timezone":"Europe/London"}}
        elif a=='get_live_categories': r=[{"category_id":"1","category_name":"News"},{"category_id":"2","category_name":"Sports"},{"category_id":"3","category_name":"FOR ADULTS 18+"},{"category_id":"4","category_name":"Adult Swim"}]
        elif a=='get_live_streams': r=LIVE+LIVE_EXTRA
        elif a=='get_vod_categories': r=[{"category_id":"10","category_name":"Action"},{"category_id":"11","category_name":"XXX Movies"}]
        elif a=='get_vod_streams': r=[{"name":"Beach Movie (2021)","stream_id":555,"stream_icon":"","rating":"7.1","container_extension":"mkv","category_id":"10"},{"name":"Sexy Beast (2000)","stream_id":556,"container_extension":"mp4","category_id":"10"},{"name":"Blue film","stream_id":557,"container_extension":"mp4","category_id":"11"}]
        elif a=='get_vod_info': r={"info":{"name":"Beach Movie","plot":"Sand."},"movie_data":{}}
        elif a=='get_series_categories': r=[{"category_id":"20","category_name":"Drama"}]
        elif a=='get_series': r=[{"name":"Beach Show","series_id":77,"cover":"c","plot":"p","cast":"A, B","genre":"Drama / Crime","releaseDate":"2020-05-01","rating":"8","backdrop_path":["bd"],"category_id":"20"}]
        elif a=='get_series_info': r={"info":{"name":"Beach Show"},"seasons":[],"episodes":{"1":[{"id":"9001","episode_num":2,"title":"E2","container_extension":"mp4","season":1,"info":{"duration_secs":1500}},{"id":"9000","episode_num":1,"title":"E1","container_extension":"mp4","season":1,"info":{}}]}}
        elif a=='get_simple_data_table':
            r={"epg_listings":[{"title":b64("Archived %d"%h),"description":b64("d"),"start":tz_str(NOW+h*3600),"start_timestamp":str(NOW+h*3600),"stop_timestamp":str(NOW+h*3600+3600),"has_archive":1 if h<0 else 0} for h in range(-50,10)]}
        else: r=[]
        self.send(json.dumps(r).encode())
def start():
    s=ThreadingHTTPServer(('127.0.0.1',0),H); threading.Thread(target=s.serve_forever,daemon=True).start(); return s
