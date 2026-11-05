#!/usr/bin/env python3
"""VPN Jackett Xray-only supervisor and local management interface."""
import http.server
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time
from urllib.parse import urlsplit

from bridge import AccessRejected, Bridge, Invalid, atomic, source_error
from network import activate

VERSION = os.getenv('JACKETT_XRAY_VERSION', 'unknown')
MODES = {'manual', 'auto', 'fallback'}


class Controller:
    def __init__(self):
        os.umask(0o077)
        self.work = Path(os.getenv('WORKDIR', '/etc/mihomo'))
        self.state_dir = self.work / '.jackett-xray'
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.ui_dir = Path('/usr/local/share/jackett-ui')
        self.state_file = self.state_dir / 'controller.json'
        self.router_config = self.state_dir / 'router.json'
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.bridge = Bridge()
        self.router = None
        self.error = ''
        self.last_refresh = None
        self.state = {'mode': 'auto', 'selected': ''}
        if self.state_file.exists():
            try:
                saved = json.loads(self.state_file.read_text())
                if saved.get('mode') in MODES: self.state['mode'] = saved['mode']
                if isinstance(saved.get('selected'), str): self.state['selected'] = saved['selected']
            except (OSError, ValueError):
                pass

    @staticmethod
    def node_id(proxy):
        return 'node-' + str(proxy['port'])

    def nodes(self):
        return [{'id': self.node_id(proxy),
                 'name': re.sub(r'^\[Xray\]\s*', '', proxy['name']),
                 'port': proxy['port']} for proxy in self.bridge.proxies]

    def _selected(self):
        ids = [node['id'] for node in self.nodes()]
        if self.state['selected'] not in ids:
            self.state['selected'] = ids[0] if ids else ''
        return self.state['selected']

    def build_router_config(self):
        nodes = self.nodes()
        if not nodes:
            raise AccessRejected('Subscription has no Xray-compatible connections')
        selected = self._selected()
        mode = self.state['mode']
        inbounds = [
            {'tag': 'socks-in', 'listen': '0.0.0.0', 'port': 1080, 'protocol': 'socks',
             'settings': {'auth': 'noauth', 'udp': True}},
            {'tag': 'http-in', 'listen': '0.0.0.0', 'port': 1081, 'protocol': 'http',
             'settings': {'allowTransparent': False}},
        ]
        if os.getenv('JACKETT_NETWORK_MODE', 'tun') == 'tun':
            inbounds.insert(0, {'tag': 'tun-in', 'port': 0, 'protocol': 'tun', 'settings': {
                'name': 'xray0', 'mtu': 1500, 'gateway': ['172.31.255.1/30'],
                'autoSystemRoutingTable': [], 'autoSystemDnsToGateway': False}})
        outbounds = [{'tag': node['id'], 'protocol': 'socks', 'settings': {'servers': [{
            'address': '127.0.0.1', 'port': node['port']} ]}} for node in nodes]
        outbounds += [{'tag': 'direct', 'protocol': 'freedom'},
                      {'tag': 'blocked', 'protocol': 'blackhole'}]
        routing = {'domainStrategy': 'AsIs', 'rules': []}
        if mode == 'manual':
            routing['rules'].append({'type': 'field', 'inboundTag': [x['tag'] for x in inbounds],
                                     'outboundTag': selected})
        else:
            strategy = 'leastping' if mode == 'auto' else 'leastload'
            settings = {} if mode == 'auto' else {'expected': 1, 'maxRTT': '5s'}
            routing['balancers'] = [{'tag': 'jackett-balance', 'selector': ['node-'],
                                     'strategy': {'type': strategy, 'settings': settings},
                                     'fallbackTag': selected}]
            routing['rules'].append({'type': 'field', 'inboundTag': [x['tag'] for x in inbounds],
                                     'balancerTag': 'jackett-balance'})
        return {
            'log': {'loglevel': 'warning'},
            'inbounds': inbounds,
            'outbounds': outbounds,
            'routing': routing,
            'observatory': {'subjectSelector': ['node-'],
                            'probeURL': os.getenv('JACKETT_PROBE_URL', 'https://www.gstatic.com/generate_204'),
                            'probeInterval': '30s', 'enableConcurrency': True},
        }

    def restart_router(self):
        config = self.build_router_config()
        candidate = self.router_config.with_suffix('.candidate.json')
        atomic(candidate, config)
        checked = subprocess.run(['/usr/local/bin/xray', 'run', '-test', '-config', str(candidate)],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if checked.returncode:
            candidate.unlink(missing_ok=True)
            raise Invalid('Xray rejected generated router configuration')
        candidate.replace(self.router_config)
        old = self.router
        if old:
            old.terminate()
            try: old.wait(timeout=5)
            except subprocess.TimeoutExpired: old.kill(); old.wait()
        self.router = subprocess.Popen(['/usr/local/bin/xray', 'run', '-config', str(self.router_config)])
        time.sleep(.35)
        if self.router.poll() is not None:
            raise Invalid('Xray router exited during startup')
        activate(str(self.work), os.getenv('JACKETT_NETWORK_MODE', 'tun'))
        atomic(self.state_file, self.state)

    def refresh(self, initial=False):
        with self.lock:
            before = [(x.get('name'), x.get('port')) for x in self.bridge.proxies]
            self.bridge.refresh()
            if self.bridge.native:
                raise Invalid('Mihomo-only subscription entries are not supported by the Xray-only image')
            after = [(x.get('name'), x.get('port')) for x in self.bridge.proxies]
            if initial or before != after:
                self.restart_router()
            self.last_refresh = int(time.time())
            self.error = ''

    def set_state(self, body):
        mode = body.get('mode', self.state['mode'])
        selected = body.get('selected', self.state['selected'])
        if mode not in MODES: raise Invalid('Unknown mode')
        ids = {node['id'] for node in self.nodes()}
        if selected not in ids: raise Invalid('Unknown node')
        with self.lock:
            previous = dict(self.state)
            self.state = {'mode': mode, 'selected': selected}
            try: self.restart_router()
            except Exception:
                self.state = previous
                raise

    def status(self):
        alive = self.router is not None and self.router.poll() is None
        return {'ready': alive, 'core': 'Xray', 'version': VERSION,
                'mode': self.state['mode'], 'selected': self._selected(),
                'nodes': self.nodes(), 'lastRefresh': self.last_refresh, 'error': self.error}

    def serve(self):
        controller = self
        class Handler(http.server.BaseHTTPRequestHandler):
            server_version = 'VPN-Jackett'
            def send_json(self, code, value):
                body = json.dumps(value, ensure_ascii=False).encode()
                self.send_response(code); self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Cache-Control', 'no-store'); self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
            def do_GET(self):
                path = urlsplit(self.path).path
                if path in ('/api/ready', '/api/status'):
                    value = controller.status()
                    self.send_json(200 if value['ready'] else 503, value); return
                relative = 'index.html' if path in ('/', '/ui', '/ui/') else path.removeprefix('/ui/').lstrip('/')
                target = (controller.ui_dir / relative).resolve()
                if controller.ui_dir not in target.parents or not target.is_file(): self.send_error(404); return
                content = target.read_bytes()
                mime = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.svg':'image/svg+xml'}.get(target.suffix,'application/octet-stream')
                self.send_response(200); self.send_header('Content-Type', mime)
                self.send_header('Cache-Control', 'no-cache' if target.suffix == '.html' else 'public, max-age=3600')
                self.send_header('X-Content-Type-Options', 'nosniff'); self.send_header('Content-Length', str(len(content))); self.end_headers(); self.wfile.write(content)
            def do_POST(self):
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if length > 4096: raise Invalid('Request too large')
                    body = json.loads(self.rfile.read(length) or b'{}')
                    if self.path == '/api/state': controller.set_state(body)
                    elif self.path == '/api/refresh': controller.refresh()
                    else: self.send_error(404); return
                    self.send_json(200, controller.status())
                except (Invalid, AccessRejected, json.JSONDecodeError) as error:
                    self.send_json(400, {'error': str(error)})
                except Exception as error:
                    controller.error = source_error(error); self.send_json(500, {'error': controller.error})
            def log_message(self, *_): pass
        server = http.server.ThreadingHTTPServer(('0.0.0.0', 9090), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    def run(self):
        self.refresh(initial=True)
        server = self.serve()
        interval = max(60, int(os.getenv('PROVIDER_INTERVAL', '3600')))
        last = time.monotonic()
        try:
            while not self.stop.wait(1):
                if self.router.poll() is not None: raise Invalid('Xray router exited')
                if any(proc.poll() is not None for proc, _ in self.bridge.running.values()):
                    raise Invalid('An Xray connection process exited')
                if time.monotonic() - last >= interval:
                    try: self.refresh()
                    except AccessRejected: raise
                    except Exception as error:
                        self.error = source_error(error)
                        print('Refresh failed; keeping active Xray configuration (' + self.error + ')', flush=True)
                    last = time.monotonic()
        finally:
            server.shutdown()

    def shutdown(self):
        self.stop.set()
        if self.router:
            self.router.terminate()
            try: self.router.wait(timeout=5)
            except subprocess.TimeoutExpired: self.router.kill(); self.router.wait()
        self.bridge.shutdown()


if __name__ == '__main__':
    controller = None
    try:
        controller = Controller()
        for sig in (signal.SIGTERM, signal.SIGINT): signal.signal(sig, lambda *_: controller.stop.set())
        controller.run()
    except Exception as error:
        print('Controller error: ' + (str(error) if isinstance(error, Invalid) else type(error).__name__), flush=True)
        raise SystemExit(1)
    finally:
        if controller: controller.shutdown()
