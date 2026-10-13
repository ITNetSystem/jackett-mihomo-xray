"""Route only forwarded RouterOS traffic into TUN; never locally created sockets."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
import yaml

TABLE = '2022'
PRIORITY = 12000

def prepare_environment(env):
    mode = env.get('JACKETT_NETWORK_MODE', 'tun').lower()
    if mode not in ('tun', 'proxy'):
        raise ValueError('JACKETT_NETWORK_MODE must be tun or proxy')
    env.update(TUN='1', TUN_AUTO_ROUTE='false', TUN_AUTO_REDIRECT='false')
    # TUN must be selected consistently even when nftables is available.
    return mode

def policy_rules(interface, ipv6=False):
    private = ['fc00::/7', 'fe80::/10', 'ff00::/8'] if ipv6 else ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '169.254.0.0/16', '224.0.0.0/4', '255.255.255.255/32']
    rules = [['priority', str(PRIORITY), 'iif', interface, 'lookup', 'main', 'suppress_prefixlength', '0']]
    rules += [['priority', str(PRIORITY + i + 1), 'iif', interface, 'to', address, 'lookup', 'main'] for i, address in enumerate(private)]
    rules.append(['priority', str(PRIORITY + 20), 'iif', interface, 'lookup', TABLE])
    return rules

def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)

def activate(workdir, mode):
    if mode == 'proxy':
        print('Network mode proxy: only explicit HTTP/SOCKS; no interception', flush=True)
        return
    config = Path(workdir) / os.getenv('CONFIG', 'default_config.yaml')
    device = None
    for _ in range(90):
        if config.exists():
            data = yaml.safe_load(config.read_text()) or {}
            listener = next((x for x in data.get('listeners', []) if x.get('name') == 'tun-in'), {})
            if listener.get('type') == 'tun':
                if listener.get('auto-route') or listener.get('auto-redirect'):
                    raise RuntimeError('Unsafe automatic TUN routing rejected')
                links = json.loads(subprocess.check_output(['ip', '-j', 'link'], text=True))
                wanted = listener.get('device', 'Meta')
                if any(x['ifname'] == wanted for x in links):
                    device = wanted
                    break
        time.sleep(1)
    if not device:
        raise RuntimeError('TUN did not start; no policy routes installed')
    defaults = json.loads(subprocess.check_output(['ip', '-j', '-4', 'route', 'show', 'default'], text=True))
    interfaces = sorted({x['dev'] for x in defaults if x.get('dev') not in ('lo', device)})
    if len(interfaces) != 1:
        raise RuntimeError('Exactly one physical default interface is required; no policy routes installed')
    for interface in interfaces:
        for family in ['-4', '-6']:
            if family == '-6':
                addresses = json.loads(subprocess.check_output(['ip', '-j', '-6', 'address', 'show', 'dev', device], text=True))
                if not any(x.get('addr_info') for x in addresses):
                    continue
            # Strict reverse-path validation rejects replies from the TUN interface.
            for dev in [interface, device, 'all']:
                path = Path('/proc/sys/net/ipv4/conf') / dev / 'rp_filter'
                if path.exists() and path.read_text().strip() != '0': path.write_text('0')
            run(['ip', family, 'route', 'replace', 'default', 'dev', device, 'table', TABLE])
            existing = json.loads(subprocess.check_output(['ip', family, '-j', 'rule'], text=True))
            if any(PRIORITY <= x.get('priority', -1) <= PRIORITY + 20 for x in existing):
                raise RuntimeError('Reserved policy priorities already occupied')
            for rule in policy_rules(interface, family == '-6'):
                run(['ip', family, 'rule', 'add', *rule])
    print('Network mode tun: forwarded traffic only; local sockets use original gateway', flush=True)

if __name__ == '__main__':
    activate(os.getenv('WORKDIR', '/etc/mihomo'), os.getenv('JACKETT_NETWORK_MODE', 'tun'))
