#!/usr/bin/env python3
"""Small Xray controller exposing the dashboard's basic Clash API."""
import base64, hashlib, http.server, json, os, socket, ssl, struct, threading, time
import urllib.parse, urllib.request
from pathlib import Path
from bridge import Bridge, Invalid, AccessRejected, atomic, source_error
import subprocess, signal

class Controller(Bridge):
    def __init__(self):
        super().__init__()
        self.lock=threading.RLock(); self.selected=''; self.active=None; self.active_digest=''; self.delays={}
        self.ui=self.work/'ui'; self.secret=os.getenv('UI_SECRET','')
    def fetch(self,key,value):
        parsed=super().fetch(key,value)
        if parsed[1]:raise Invalid("Compact supports Xray profiles only; native Mihomo entries cannot be used")
        return parsed
    def refresh(self):
        super().refresh()
        names=[p['name'] for p in self.proxies]
        if self.selected not in names:
            saved=self.work/'selected.json'
            prior=json.loads(saved.read_text()) if saved.exists() else ''
            self.selected=prior if prior in names else names[0]
        self.activate(self.selected)
    def activate(self,name):
        proxy=next((p for p in self.proxies if p['name']==name),None)
        if not proxy: raise Invalid('Unknown proxy')
        config=json.loads((self.state/('node-'+str(proxy['port'])+'.json')).read_text())
        config['inbounds']=[{'tag':'jackett-local','listen':'0.0.0.0','port':int(os.getenv('MIXED_PORT','1080')),'protocol':'socks','settings':{'auth':'noauth','udp':True}}, {'tag':'jackett-local-http','listen':'0.0.0.0','port':int(os.getenv('HTTP_PORT','1081')),'protocol':'http','settings':{}}]
        for rule in config.get('routing',{}).get('rules',[]):
            if 'jackett-local' in rule.get('inboundTag',[]): rule['inboundTag'].append('jackett-local-http')
        digest=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
        if self.active and self.active.poll() is None and self.active_digest==digest:
            self.selected=name;atomic(self.work/'selected.json',name);return
        path=self.state/'selected-config.json'; atomic(path,config)
        result=subprocess.run(['/usr/local/bin/xray','run','-test','-config',str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if result.returncode: raise Invalid('Selected Xray configuration rejected')
        if self.active:
            self.active.terminate()
            try:self.active.wait(timeout=5)
            except subprocess.TimeoutExpired:self.active.kill();self.active.wait()
        self.active=subprocess.Popen(['/usr/local/bin/xray','run','-config',str(path)])
        self.active_digest=digest
        self.selected=name; atomic(self.work/'selected.json',name)
    def node(self,p):
        return {'name':p['name'],'type':'Socks5','udp':True,'history':self.delays.get(p['name'],[]),'alive':bool(self.delays.get(p['name']))}
    def proxies_body(self):
        nodes={p['name']:self.node(p) for p in self.proxies}
        nodes['SELECTOR']={'name':'SELECTOR','type':'Selector','now':self.selected,'all':list(nodes),'history':[]}
        nodes['GLOBAL']={'name':'GLOBAL','type':'Selector','now':'SELECTOR','all':['SELECTOR'],'history':[]}
        return {'proxies':nodes}
    def providers_body(self):
        return {'providers':{key:{'name':key,'type':'Proxy','vehicleType':'HTTP','proxies':[self.node(p) for p in value['proxies']]} for key,value in self.providers.items()}}
    def delay(self,name,target,timeout):
        p=next((p for p in self.proxies if p['name']==name),None)
        if not p:raise Invalid('Unknown proxy')
        u=urllib.parse.urlsplit(target)
        if u.scheme not in ('http','https') or not u.hostname:raise Invalid('Invalid test URL')
        host=u.hostname.encode('idna');port=u.port or (443 if u.scheme=='https' else 80)
        start=time.monotonic()
        def exact(s,n):
            data=b''
            while len(data)<n:
                part=s.recv(n-len(data))
                if not part:raise Invalid('SOCKS connection closed')
                data+=part
            return data
        with socket.create_connection(('127.0.0.1',p['port']),timeout) as s:
            s.sendall(b'\x05\x01\x00')
            if exact(s,2)!=b'\x05\x00':raise Invalid('SOCKS authentication failed')
            s.sendall(b'\x05\x01\x00\x03'+bytes([len(host)])+host+struct.pack('!H',port))
            reply=exact(s,4)
            if reply[1]:raise Invalid('Proxy connection failed')
            size={1:4,4:16}.get(reply[3])
            if reply[3]==3:size=exact(s,1)[0]
            if size is None:raise Invalid('Invalid SOCKS reply')
            exact(s,size+2)
            if u.scheme=='https':s=ssl.create_default_context().wrap_socket(s,server_hostname=u.hostname)
            s.sendall(('GET '+(u.path or '/')+('?' + u.query if u.query else '')+' HTTP/1.1\r\nHost: '+u.netloc+'\r\nConnection: close\r\n\r\n').encode())
            data=s.recv(4096)
            if not data.startswith(b'HTTP/'):raise Invalid('Invalid HTTP response')
        elapsed=max(1,int((time.monotonic()-start)*1000))
        self.delays[name]=[{'time':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'delay':elapsed}]
        return elapsed
    def shutdown(self):
        if self.active:
            self.active.terminate()
            try:self.active.wait(timeout=5)
            except subprocess.TimeoutExpired:self.active.kill();self.active.wait()
        super().shutdown()

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def respond(self,body,status=200):
        raw=json.dumps(body,ensure_ascii=False).encode();self.send_response(status)
        self.send_header('Content-Type','application/json');self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_OPTIONS(self):
        self.send_response(204);self.send_header('Access-Control-Allow-Origin','*');self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type');self.send_header('Access-Control-Allow-Methods','GET, PUT, PATCH, POST, DELETE, OPTIONS');self.end_headers()
    def do_GET(self):self.handle_api()
    def do_PUT(self):self.handle_api()
    def do_PATCH(self):self.handle_api()
    def handle_api(self):
        c=self.server.controller;u=urllib.parse.urlsplit(self.path);path=urllib.parse.unquote(u.path);query=urllib.parse.parse_qs(u.query)
        if path=='/ui':
            self.send_response(302);self.send_header('Location','/ui/');self.end_headers();return
        if path.startswith('/ui/'):
            root=(c.ui/'dist' if (c.ui/'dist/index.html').is_file() else c.ui).resolve();file=(root/(path[4:] or 'index.html')).resolve()
            if not file.is_relative_to(root) or not file.is_file():self.respond({'message':'Not found'},404);return
            import mimetypes
            raw=file.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(str(file))[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
        if c.secret and self.headers.get('Authorization')!='Bearer '+c.secret:
            self.respond({'message':'Unauthorized'},401);return
        try:
            if self.command=='GET':
                if path=='/version':body={'version':'Jackett-compact-Xray26.10.10','meta':True}
                elif path=='/configs':body={'mode':'global','port':int(os.getenv('HTTP_PORT','1081')),'socks-port':int(os.getenv('MIXED_PORT','1080')),'mixed-port':0,'allow-lan':True,'log-level':os.getenv('LOG_LEVEL','info'),'ipv6':True,'tun':{'enable':False}}
                elif path=='/proxies':body=c.proxies_body()
                elif path=='/providers/proxies':body=c.providers_body()
                elif path.startswith('/providers/proxies/'):body=c.providers_body()['providers'][path.split('/',3)[3]]
                elif path.startswith('/proxies/') and path.endswith('/delay'):
                    name=path[len('/proxies/'):-len('/delay')];body={'delay':c.delay(name,query.get('url',['https://www.gstatic.com/generate_204'])[0],min(30,max(1,int(query.get('timeout',['5000'])[0])/1000)))}
                elif path.startswith('/proxies/'):body=c.proxies_body()['proxies'][path[len('/proxies/'):]]
                elif path=='/rules':body={'rules':[]}
                elif path=='/providers/rules':body={'providers':{}}
                elif path=='/connections':self.respond({'message':'Connection statistics unavailable in compact'},501);return
                else:self.respond({'message':'Unsupported endpoint'},404);return
                self.respond(body)
            elif self.command=='PUT' and path=='/proxies/SELECTOR':
                size=int(self.headers.get('Content-Length','0'))
                if size>4096:raise Invalid('Request too large')
                body=json.loads(self.rfile.read(size))
                with c.lock:c.activate(body['name'])
                self.respond({})
            elif self.command=='PUT' and path=='/proxies/GLOBAL':
                size=int(self.headers.get('Content-Length','0'))
                if size>4096:raise Invalid('Request too large')
                if json.loads(self.rfile.read(size)).get('name')!='SELECTOR':raise Invalid('Only SELECTOR is available')
                self.respond({})
            elif self.command=='PUT' and path.startswith('/providers/proxies/'):
                with c.lock:c.refresh()
                self.respond({})
            else:self.respond({'message':'Setting is unsupported in compact'},501)
        except (KeyError,Invalid,ValueError) as e:self.respond({'message':source_error(e)},400)
        except Exception as e:self.respond({'message':source_error(e)},502)

def main():
    c=Controller()
    try:
        c.refresh()
        # Dashboard is optional; failure must not prevent the proxy from starting.
        ui_url=os.getenv('EXTERNAL_UI_URL','https://github.com/Zephyruso/zashboard/releases/latest/download/dist-cdn-fonts.zip')
        if ui_url:
            def download_ui():
                import io,zipfile
                try:
                    with urllib.request.urlopen(ui_url,timeout=30) as r:raw=r.read(32*1024*1024+1)
                    if len(raw)>32*1024*1024:raise Invalid('UI archive too large')
                    c.ui.mkdir(parents=True,exist_ok=True)
                    with zipfile.ZipFile(io.BytesIO(raw)) as z:
                        if sum(i.file_size for i in z.infolist())>64*1024*1024:raise Invalid('UI archive expands too much')
                        for i in z.infolist():
                            dest=(c.ui/i.filename).resolve()
                            if not dest.is_relative_to(c.ui.resolve()):raise Invalid('Invalid UI archive path')
                        z.extractall(c.ui)
                    print('Dashboard ready',flush=True)
                except Exception as e:print('UI download failed ('+source_error(e)+')',flush=True)
            threading.Thread(target=download_ui,daemon=True).start()
        server=http.server.ThreadingHTTPServer(('0.0.0.0',int(os.getenv('UI_PORT','9090'))),Handler);server.controller=c
        threading.Thread(target=server.serve_forever,daemon=True).start()
        for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:c.stop.set())
        last=time.monotonic()
        while not c.stop.wait(1):
            if c.active.poll() is not None or any(p.poll() is not None for p,_ in c.running.values()):raise Invalid('Xray exited')
            if time.monotonic()-last>=max(60,int(os.getenv('PROVIDER_INTERVAL','3600'))):
                try:
                    with c.lock:c.refresh()
                except AccessRejected:raise
                except Exception as e:print('Refresh failed ('+source_error(e)+')',flush=True)
                last=time.monotonic()
        server.shutdown()
    finally:c.shutdown()
if __name__=='__main__':main()
