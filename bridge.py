#!/usr/bin/env python3
"""ENV subscription adapter. Remote credentials never enter the Mihomo provider."""
import base64
import copy
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import signal
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse as url
import urllib.request
import urllib.error
import uuid
import yaml

MAX_BYTES = 8 * 1024 * 1024
MAX_PROFILES = 64
NATIVE = {'ssr', 'tuic', 'hysteria', 'anytls', 'ssh', 'snell', 'mieru', 'awg', 'amneziawg'}

class Invalid(ValueError):
    pass

class AccessRejected(Invalid):
    pass

def b64(s):
    return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4)).decode()

def stream(q, host):
    network = q.get('type', q.get('network', 'tcp'))
    network = {'tcp':'raw', 'ws':'ws', 'websocket':'ws', 'splithttp':'xhttp', 'mkcp':'kcp'}.get(network, network)
    if network not in {'raw','xhttp','grpc','ws','httpupgrade','kcp'}:
        raise Invalid('Use native Xray JSON for this transport')
    s = {'network':network, 'security':q.get('security','none')}
    if s['security'] == 'tls':
        s['tlsSettings'] = {'serverName':q.get('sni',host), 'fingerprint':q.get('fp','chrome'), 'allowInsecure':q.get('allowInsecure',q.get('insecure','0')).lower() in ('1','true')}
        if q.get('alpn'): s['tlsSettings']['alpn'] = q['alpn'].split(',')
        for key,field in [('ech','echConfigList'),('vcn','verifyPeerCertByName'),('pcs','pinnedPeerCertSha256')]:
            if q.get(key): s['tlsSettings'][field]=q[key]
    elif s['security'] == 'reality':
        s['realitySettings'] = {'serverName':q.get('sni',host), 'fingerprint':q.get('fp','chrome'), 'publicKey':q.get('pbk',''), 'shortId':q.get('sid',''), 'spiderX':q.get('spx','')}
        if q.get('pqv'): s['realitySettings']['mldsa65Verify']=q['pqv']
    elif s['security'] != 'none':
        raise Invalid('Unknown transport security')
    if network == 'xhttp':
        s['xhttpSettings'] = {'path':q.get('path','/'), 'host':q.get('host',''), 'mode':q.get('mode','auto')}
        if q.get('extra'):
            extra = json.loads(q['extra'])
            if not isinstance(extra,dict): raise Invalid('Invalid XHTTP extra')
            s['xhttpSettings'].update(extra)
        if q.get('x_padding_bytes'): s['xhttpSettings']['xPaddingBytes']=q['x_padding_bytes']
        for field in ('xPaddingBytes','scMaxEachPostBytes','scMinPostsIntervalMs','uplinkChunkSize'):
            if q.get(field): s['xhttpSettings'][field]=q[field]
    elif network == 'grpc':
        s['grpcSettings'] = {'serviceName':q.get('serviceName',''), 'multiMode':q.get('mode','gun')=='multi'}
        if q.get('authority'): s['grpcSettings']['authority'] = q['authority']
    elif network in ('ws','httpupgrade'):
        settings = {'path':q.get('path','/')}
        if network == 'ws': settings['headers'] = {'Host':q.get('host',host)}
        else: settings['host'] = q.get('host',host)
        if q.get('ed'): settings['maxEarlyData'] = int(q['ed'])
        if q.get('eh'): settings['earlyDataHeaderName'] = q['eh']
        s[network+'Settings'] = settings
    elif network == 'kcp':
        s['kcpSettings'] = {'header':{'type':q.get('headerType','none')}}
        if q.get('seed'): s['kcpSettings']['seed'] = q['seed']
    elif q.get('headerType','none') != 'none':
        if q['headerType'] != 'http': raise Invalid('Use JSON for this raw header')
        s['rawSettings'] = {'header':{'type':'http', 'request':{'path':[q.get('path','/')], 'headers':{'Host':q.get('host',host).split(',')}}}}
    if q.get('fm'):
        mask=json.loads(q['fm'])
        if not isinstance(mask,dict): raise Invalid('Invalid FinalMask')
        s['finalmask']=mask
    allowed = {'type','network','security','sni','fp','pbk','sid','spx','alpn','allowInsecure','insecure','path','host','mode','extra','serviceName','authority','ed','eh','seed','headerType','flow','encryption','x_padding_bytes','xPaddingBytes','scMaxEachPostBytes','scMinPostsIntervalMs','uplinkChunkSize','support-x25519mlkem768','pqv','ech','vcn','pcs','fm'}
    if set(q)-allowed: raise Invalid('Unknown URI parameter; use Xray JSON to preserve it')
    return s

def source_error(error):
    """Explain network failures without logging URLs or credential-bearing text."""
    if isinstance(error, Invalid): return str(error)
    if isinstance(error, urllib.error.HTTPError): return 'HTTP '+str(error.code)
    reason = error.reason if isinstance(error, urllib.error.URLError) else error
    if isinstance(reason, ssl.SSLCertVerificationError): return 'TLS certificate verification failed'
    if isinstance(reason, ssl.SSLError): return 'TLS handshake failed'
    if isinstance(reason, socket.gaierror): return 'DNS resolution failed'
    if isinstance(reason, TimeoutError): return 'connection/read timed out; check gateway, NAT, firewall and hairpin'
    if isinstance(reason, ConnectionRefusedError): return 'connection refused'
    if isinstance(reason, ConnectionResetError): return 'connection reset'
    if isinstance(reason, OSError): return 'network error (errno '+str(reason.errno)+')'
    return type(error).__name__

def uri_profile(link):
    # WireGuard keys are base64, not form data. Accept raw / + = in
    # userinfo and query, and percent-decode exactly once.
    wg = re.match(r'^(wireguard|wg)://([^@]+)@', link)
    if wg:
        link = wg.group(1)+'://'+url.quote(url.unquote(wg.group(2)),safe='')+'@'+link[wg.end():]
    u = url.urlsplit(link)
    if u.scheme in NATIVE: return None
    if u.scheme == 'vmess':
        v = json.loads(b64(link[8:]))
        if set(v)-{'v','ps','add','port','id','aid','scy','net','type','host','path','tls','sni','fp','alpn'}: raise Invalid('Unknown VMess option; use Xray JSON')
        if v.get('type','none') not in ('','none','http'): raise Invalid('Advanced VMess transport requires Xray JSON')
        q = {'type':v.get('net','tcp'), 'security':v.get('tls','none') or 'none', 'host':v.get('host',''), 'path':v.get('path','/'), 'sni':v.get('sni',v['add']), 'fp':v.get('fp','chrome')}
        if v.get('type')=='http':
            if q['type'] not in ('tcp','raw'): raise Invalid('VMess HTTP header requires raw transport')
            q['headerType']='http'
        if v.get('alpn'): q['alpn']=v['alpn']
        if q['type']=='grpc': q['serviceName']=v.get('path','')
        out = {'protocol':'vmess','settings':{'vnext':[{'address':v['add'],'port':int(v['port']),'users':[{'id':v['id'],'alterId':int(v.get('aid',0)),'security':v.get('scy','auto')}]}]},'streamSettings':stream(q,v['add'])}
        return v.get('ps','VMess'), {'outbounds':[out]}
    query = u.query.replace('+','%2B') if u.scheme in ('wireguard','wg') else u.query
    q = dict(url.parse_qsl(query,keep_blank_values=True))
    name = url.unquote(u.fragment) or u.scheme.upper()
    if u.scheme == 'ss':
        if q: raise Invalid('Shadowsocks plugins require a native configuration')
        authority = link[5:].split('#',1)[0]
        if '@' not in authority: authority = b64(authority)
        credentials, endpoint = authority.rsplit('@',1)
        credentials = url.unquote(credentials)
        if ':' not in credentials: credentials = b64(credentials)
        method,password = credentials.split(':',1)
        target=url.urlsplit('ss://'+endpoint)
        out={'protocol':'shadowsocks','settings':{'servers':[{'address':target.hostname,'port':target.port,'method':method,'password':password}]}}
    else:
        if not u.hostname or (not u.port and u.scheme not in ('hysteria2','hy2')): raise Invalid('Missing address or port')
        credential = url.unquote(u.username or '')
        if u.scheme in ('vless','trojan'):
            s = stream(q,u.hostname)
            if u.scheme=='vless':
                user={'id':str(uuid.UUID(credential)), 'encryption':q.get('encryption','none')}
                if q.get('flow'): user['flow']=q['flow']
                out={'protocol':'vless','settings':{'vnext':[{'address':u.hostname,'port':u.port,'users':[user]}]},'streamSettings':s}
            else:
                out={'protocol':'trojan','settings':{'servers':[{'address':u.hostname,'port':u.port,'password':credential}]},'streamSettings':s}
        elif u.scheme in ('socks','socks5','http','https'):
            if q: raise Invalid('Use JSON for proxy parameters')
            server={'address':u.hostname,'port':u.port}
            if credential: server['users']=[{'user':credential,'pass':url.unquote(u.password or '')}]
            out={'protocol':'http' if u.scheme.startswith('http') else 'socks','settings':{'servers':[server]}}
            if u.scheme=='https': out['streamSettings']={'network':'raw','security':'tls','tlsSettings':{'serverName':u.hostname}}
        elif u.scheme in ('hysteria2','hy2'):
            allowed={'security','sni','alpn','fp','insecure','allowInsecure'}
            if set(q)-allowed: raise Invalid('Use Xray JSON for Hysteria2 obfuscation/advanced options')
            if q.get('security','tls')!='tls': raise Invalid('Hysteria2 requires TLS')
            auth=credential+(':'+url.unquote(u.password) if u.password is not None else '')
            tls={'serverName':q.get('sni',u.hostname),'alpn':q.get('alpn','h3').split(','),'allowInsecure':q.get('insecure',q.get('allowInsecure','0')).lower() in ('1','true')}
            if q.get('fp'): tls['fingerprint']=q['fp']
            out={'protocol':'hysteria','settings':{'version':2,'address':u.hostname,'port':u.port or 443},'streamSettings':{'network':'hysteria','security':'tls','hysteriaSettings':{'version':2,'auth':auth},'tlsSettings':tls}}
        elif u.scheme in ('wireguard','wg'):
            allowed={'address','ip','publickey','publicKey','public_key','allowedips','allowed_ips','presharedkey','psk','keepalive','mtu','reserved','dns'}
            if set(q)-allowed: raise Invalid('Use Xray JSON for advanced WireGuard options')
            addresses=q.get('address',q.get('ip','')).split(',')
            if not addresses[0]: raise Invalid('WireGuard tunnel address is required')
            host=('['+u.hostname+']') if ':' in u.hostname else u.hostname
            peer={'publicKey':q.get('publickey',q.get('publicKey',q.get('public_key',''))),'endpoint':host+':'+str(u.port),'allowedIPs':q.get('allowedips',q.get('allowed_ips','0.0.0.0/0,::/0')).split(',')}
            if q.get('presharedkey',q.get('psk')): peer['preSharedKey']=q.get('presharedkey',q.get('psk'))
            if q.get('keepalive'): peer['keepAlive']=int(q['keepalive'])
            settings={'secretKey':credential,'address':addresses,'peers':[peer],'noKernelTun':True}
            if q.get('mtu'): settings['mtu']=int(q['mtu'])
            if q.get('reserved'): settings['reserved']=[int(x) for x in q['reserved'].split(',')]
            out={'protocol':'wireguard','settings':settings}
            if q.get('dns'): settings['remoteDNS']=q['dns'].split(',')
        else:
            raise Invalid('Use Xray JSON or supported Mihomo YAML for this protocol')
    out['tag']='proxy'
    return name, {'outbounds':[out]}

def parse_payload(text, source):
    text=text.strip()
    if len(text.encode())>MAX_BYTES: raise Invalid('Subscription too large')
    if text.startswith(('{','[')):
        payload=json.loads(text)
        if isinstance(payload,dict) and isinstance(payload.get('proxies'),list): return [],payload['proxies']
        items=payload if isinstance(payload,list) else [payload]
        result=[]
        for i,item in enumerate(items):
            if not isinstance(item,dict): raise Invalid('Expected Xray configuration object')
            if 'protocol' in item: item={'outbounds':[item]}
            if not isinstance(item.get('outbounds'),list) or not item['outbounds']: raise Invalid('Missing Xray outbounds')
            name=item.get('remarks',item.get('remark',item.get('name',source+'-'+str(i+1))))
            result.append((str(name),item))
        return result, []
    if text.startswith('proxies:') or '\nproxies:' in text:
        # Keep native YAML intact rather than silently dropping unsupported options.
        p=yaml.safe_load(text)
        if not isinstance(p,dict) or not isinstance(p.get('proxies'),list): raise Invalid('Invalid Mihomo YAML')
        return [], p['proxies']
    if '://' not in text:
        text=b64(''.join(text.split()))
        if text.lstrip().startswith(('{','[')): return parse_payload(text,source)
    result=[]; native=[]
    for line in text.splitlines():
        line=line.strip()
        if not line or line.startswith('#') or line.startswith(('happ://','incy://routing/')): continue
        profile=uri_profile(line)
        if profile is None: native.append(line)
        else: result.append(profile)
    return result,native

def local_config(profile,port):
    c=copy.deepcopy(profile)
    old_tags={x.get('tag') for x in c.get('inbounds',[]) if x.get('tag')}
    c['inbounds']=[{'tag':'jackett-local','listen':'127.0.0.1','port':port,'protocol':'socks','settings':{'auth':'noauth','udp':True}}]
    for rule in c.get('routing',{}).get('rules',[]):
        tags=rule.get('inboundTag',[])
        if isinstance(tags,list) and old_tags.intersection(tags): rule['inboundTag']=['jackett-local']
    # Remove external management listeners; preserve native protocol/transport fields.
    for key in ('api','metrics','reverse','remarks','remark','name'): c.pop(key,None)
    for outbound in c.get('outbounds',[]):
        if outbound.get('protocol')=='wireguard':
            outbound.setdefault('settings',{}).setdefault('noKernelTun',True)
    c['log']={'loglevel':'warning'}
    return c

def atomic(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False));temp.chmod(0o600);temp.replace(path)

class Bridge:
    def __init__(self):
        os.umask(0o077)
        self.work=Path(os.getenv('WORKDIR','/etc/mihomo'))
        self.state=self.work/'.jackett-xray';self.state.mkdir(parents=True,exist_ok=True)
        self.running={};self.proxies=[];self.native=[];self.providers={};self.stop=threading.Event()
        self.sources={k:v for k,v in os.environ.items() if re.fullmatch(r'(SUB|SRV|XRAY_JSON)[0-9]+(?:_[A-Za-z0-9]+)?',k) and v}
        if not self.sources: raise Invalid('Add SUB1, SRV1 or XRAY_JSON1')
        self.hwid=os.getenv('HWID','')
        if not self.hwid:
            hp=self.work/'.hwid'
            if not hp.exists(): hp.write_text(uuid.uuid4().hex)
            self.hwid=hp.read_text().strip()
        self.mapping={}
        if (self.state/'ports.json').exists(): self.mapping=json.loads((self.state/'ports.json').read_text())

    def fetch(self,key,value):
        if value.startswith(('https://','http://')):
            req=urllib.request.Request(value,headers={'User-Agent':os.getenv('SUB_USER_AGENT','Happ/1.0 Jackett-Bridge'), 'x-hwid':self.hwid, 'Accept':'application/json,text/plain'})
            with urllib.request.urlopen(req,timeout=30) as r:
                raw=r.read(MAX_BYTES+1)
            if len(raw)>MAX_BYTES: raise Invalid('Subscription too large')
            value=raw.decode('utf-8-sig')
        return parse_payload(value,key)

    def refresh(self):
        profiles=[];native=[];pending_cache=[];providers={}
        for key,value in sorted(self.sources.items()):
            # Cache indexed by source, without storing the URL in logs or cache names.
            cache=self.state/('source-'+hashlib.sha256((key+value).encode()).hexdigest()[:20]+'.json')
            try:
                parsed=self.fetch(key,value)
                pending_cache.append((cache,parsed))
            except Exception as e:
                rejected=isinstance(e,urllib.error.HTTPError) and e.code in (401,403,404)
                if rejected or not cache.exists():
                    if rejected: cache.unlink(missing_ok=True)
                    print('Cannot load '+key+' ('+source_error(e)+'); source disabled',flush=True)
                    providers[key]={'proxies':[],'native':[]}
                    continue
                print('Keeping last valid source '+key+' ('+source_error(e)+')',flush=True)
                parsed=json.loads(cache.read_text())
            source_native=parsed[1]
            if any(isinstance(x,str) for x in source_native) and any(isinstance(x,dict) for x in source_native):
                raise Invalid('Do not mix native URI and native YAML within one source: '+key)
            providers[key]={'proxies':[],'native':source_native}
            for index,(name,config) in enumerate(parsed[0]):
                identity=key+':'+name+':'+str(index)
                profiles.append((key,identity,name,config))
            native.extend(parsed[1])
        if len(profiles)>MAX_PROFILES: raise Invalid('Maximum 64 Xray connections')
        if not profiles and not native: raise AccessRejected('Subscription has no usable connections; refusing direct fallback')
        desired={};proxies=[];names=set()
        for key,ident,name,config in profiles:
            if ident not in self.mapping:
                used=set(self.mapping.values());self.mapping[ident]=next((x for x in range(20000,21000) if x not in used),None)
                if self.mapping[ident] is None: raise Invalid('Local port pool exhausted')
            port=self.mapping[ident]
            c=local_config(config,port)
            path=self.state/('node-'+str(port)+'.json');candidate=path.with_suffix('.candidate.json')
            atomic(candidate,c)
            check=subprocess.run(['/usr/local/bin/xray','run','-test','-config',str(candidate)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            if check.returncode: raise Invalid('Xray rejected '+str(port)+'; check source parameters (credentials omitted)')
            candidate.unlink()
            digest=hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()
            desired[port]=(digest,c,path)
            name='[Xray] '+name
            if name in names: name+=' ('+str(port)+')'
            names.add(name)
            proxy={'name':name,'type':'socks5','server':'127.0.0.1','port':port,'udp':True}
            proxies.append(proxy);providers[key]['proxies'].append(proxy)
        # Validation completes before changing any running connection.
        for cache,parsed in pending_cache: atomic(cache,parsed)
        for port,(proc,digest) in list(self.running.items()):
            if port not in desired or desired[port][0]!=digest:
                proc.terminate()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: proc.kill();proc.wait()
                del self.running[port]
        for port,(digest,c,path) in desired.items():
            if port not in self.running:
                atomic(path,c)
                proc=subprocess.Popen(['/usr/local/bin/xray','run','-config',str(path)])
                self.running[port]=(proc,digest)
        self.proxies=proxies;self.native=native;self.providers=providers
        hook=['saved_interval=$PROVIDER_INTERVAL','PROVIDER_INTERVAL=60',
              '[ -n "$PROVIDERS_BLOCK" ] || PROVIDERS_LIST=""']
        for key in sorted(providers):
            hook.append('add_provider '+key+' http http://127.0.0.1:18890/providers/'+key+' false')
            hook.append('PROVIDERS_BLOCK="${PROVIDERS_BLOCK}    proxy: DIRECT\n"')
        hook.append('PROVIDER_INTERVAL=$saved_interval')
        hook_path=self.work/'user_sh'/'jackett-all-xray.sh'
        hook_path.parent.mkdir(parents=True,exist_ok=True)
        hook_path.write_text('\n'.join(hook)+'\n')
        atomic(self.state/'ports.json',self.mapping)
        atomic(self.work/'jackett-native.json',{'proxies':[x for x in native if isinstance(x,dict)]})
        (self.work/'jackett-native-links.txt').write_text('\n'.join(x for x in native if isinstance(x,str)))
        print('Bridge ready: '+str(len(proxies))+' Xray connections, '+str(len(native))+' native Mihomo entries',flush=True)

    def shutdown(self):
        self.stop.set()
        for proc,_ in self.running.values(): proc.terminate()
        for proc,_ in self.running.values():
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill();proc.wait()

    def provider_body(self,key):
        provider=self.providers[key]
        proxies=provider['proxies'];native=provider['native']
        links=[x for x in native if isinstance(x,str)]
        if links:
            local=['socks5://127.0.0.1:'+str(x['port'])+'#'+url.quote(x['name']) for x in proxies]
            return ('\n'.join(local+links)).encode()
        return json.dumps({'proxies':proxies+[x for x in native if isinstance(x,dict)]},ensure_ascii=False).encode()

    def run(self):
        self.refresh()
        bridge=self
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path=='/ready':
                    body=b'{"ready":true}'
                elif self.path.startswith('/providers/') and self.path[11:] in bridge.providers:
                    body=bridge.provider_body(self.path[11:])
                elif self.path=='/proxies':
                    # Compatibility view; runtime hooks use separate source endpoints.
                    body=json.dumps({'proxies':bridge.proxies+[x for x in bridge.native if isinstance(x,dict)]},ensure_ascii=False).encode()
                    if any(isinstance(x,str) for x in bridge.native):
                        if any(isinstance(x,dict) for x in bridge.native): self.send_error(409);return
                        local=['socks5://127.0.0.1:'+str(x['port'])+'#'+url.quote(x['name']) for x in bridge.proxies]
                        body=('\n'.join(local+[x for x in bridge.native if isinstance(x,str)])).encode()
                else:
                    self.send_error(404);return
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def log_message(self,*args): pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',18890),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        interval=max(60,int(os.getenv('PROVIDER_INTERVAL','3600')))
        last=time.monotonic()
        while not self.stop.wait(1):
            if any(p.poll() is not None for p,_ in self.running.values()):
                raise Invalid('An Xray connection process exited; refusing a silent direct fallback')
            if time.monotonic()-last>=interval:
                try: self.refresh()
                except AccessRejected: raise
                except Exception as e: print('Refresh failed; retaining active configurations ('+source_error(e)+')',flush=True)
                last=time.monotonic()
        server.shutdown()

if __name__=='__main__':
    bridge=None
    try:
        bridge=Bridge()
        for sig in (signal.SIGTERM,signal.SIGINT): signal.signal(sig,lambda *_:bridge.stop.set())
        bridge.run()
    except Exception as e:
        print('Bridge error: '+(str(e) if isinstance(e,Invalid) else type(e).__name__),file=sys.stderr,flush=True)
        sys.exit(1)
    finally:
        if bridge: bridge.shutdown()
