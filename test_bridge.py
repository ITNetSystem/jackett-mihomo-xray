import base64
import copy
import json
import unittest
from bridge import Invalid, local_config, parse_payload, uri_profile, source_error, Bridge

ID='11111111-1111-4111-8111-111111111111'
class ConversionTests(unittest.TestCase):
    def vless(self,q):
        return uri_profile('vless://'+ID+'@vpn.example:443?'+q+'#Location')[1]
    def test_tcp_flow_reality(self):
        c=self.vless('type=tcp&security=reality&pbk=abc&sid=0123&sni=mail.example&flow=xtls-rprx-vision')
        o=c['outbounds'][0]
        self.assertEqual(o['settings']['vnext'][0]['users'][0]['flow'],'xtls-rprx-vision')
        self.assertEqual(o['streamSettings']['realitySettings']['shortId'],'0123')
    def test_grpc_and_xhttp_parameters(self):
        c=self.vless('type=grpc&security=tls&serviceName=service&mode=multi')
        self.assertEqual(c['outbounds'][0]['streamSettings']['grpcSettings'],{'serviceName':'service','multiMode':True})
        c=self.vless('type=xhttp&security=tls&path=%2Fx&extra=%7B%22scMaxEachPostBytes%22%3A1000%7D')
        self.assertEqual(c['outbounds'][0]['streamSettings']['xhttpSettings']['scMaxEachPostBytes'],1000)
    def test_unknown_options_are_not_dropped(self):
        with self.assertRaises(Invalid): self.vless('type=tcp&newOption=secret')
    def test_base64_subscription_and_native_split(self):
        raw='vless://'+ID+'@vpn.example:443?security=tls#X\ntuic://user:pass@tuic.example:443#T'
        a,b=parse_payload(base64.b64encode(raw.encode()).decode(),'SUB1')
        self.assertEqual(len(a),1);self.assertEqual(len(b),1)
    def test_full_json_preserves_transport_and_dependencies(self):
        p={'remarks':'A','inbounds':[{'tag':'old'}],'dns':{'servers':['1.1.1.1']},'outbounds':[{'tag':'proxy','protocol':'vless','settings':{},'streamSettings':{'network':'xdrive','xdriveSettings':{'secrets':['private']},'finalmask':{'tcp':[{'type':'fragment'}]}}},{'tag':'direct','protocol':'freedom'}],'routing':{'rules':[{'inboundTag':['old'],'outboundTag':'proxy'}]}}
        before=copy.deepcopy(p);c=local_config(p,20000)
        self.assertEqual(p,before)
        self.assertEqual(c['outbounds'],p['outbounds']);self.assertEqual(c['dns'],p['dns'])
        self.assertEqual(c['routing']['rules'][0]['inboundTag'],['jackett-local'])
        self.assertEqual(c['inbounds'][0]['listen'],'127.0.0.1')
    def test_native_yaml_keeps_unsupported_parameters(self):
        a,b=parse_payload('proxies:\n- name: T\n  type: tuic\n  server: example\n  port: 443\n  uuid: test\n  password: private\n','SUB1')
        self.assertEqual(a,[]);self.assertEqual(b[0]['password'],'private')
    def test_hysteria2(self):
        _,p=uri_profile('hy2://secret@vpn.example:443?sni=mail.example#H')
        self.assertEqual(p['outbounds'][0]['streamSettings']['hysteriaSettings']['auth'],'secret')
    def test_ss_sip002(self):
        auth=base64.urlsafe_b64encode(b'aes-128-gcm:secret').decode().rstrip('=')
        _,p=uri_profile('ss://'+auth+'@vpn.example:443#S')
        self.assertEqual(p['outbounds'][0]['settings']['servers'][0]['password'],'secret')
    def test_wireguard_raw_and_encoded_keys(self):
        from urllib.parse import quote
        private=base64.b64encode(bytes([251])*32).decode()
        public=base64.b64encode(bytes([255])*32).decode()
        psk=base64.b64encode(bytes([250])*32).decode()
        for scheme in ('wireguard','wg'):
            for encode in (lambda x:x, lambda x:quote(x,safe='')):
                link=scheme+'://'+encode(private)+'@[2001:db8::1]:51820?address=10.7.0.2/32&publickey='+encode(public)+'&psk='+encode(psk)+'&allowedips=0.0.0.0/0&keepalive=25#WG'
                with self.subTest(scheme=scheme,encoded=encode(private)!=private):
                    _,c=uri_profile(link);w=c['outbounds'][0]['settings']
                    self.assertEqual(w['secretKey'],private)
                    self.assertEqual(w['peers'][0]['publicKey'],public)
                    self.assertEqual(w['peers'][0]['preSharedKey'],psk)
                    self.assertEqual(w['peers'][0]['endpoint'],'[2001:db8::1]:51820')
                    profiles,_=parse_payload(base64.b64encode(link.encode()).decode(),'SUB1')
                    self.assertEqual(profiles[0][1]['outbounds'][0]['settings'],w)

    def test_network_error_diagnostics_do_not_expose_url(self):
        import socket, ssl, urllib.error
        cases=[(socket.gaierror(-2,'private-url'),'DNS resolution failed'),
               (TimeoutError('private-url'),'connection/read timed out'),
               (ssl.SSLCertVerificationError('private-url'),'TLS certificate verification failed')]
        for reason,expected in cases:
            message=source_error(urllib.error.URLError(reason))
            self.assertIn(expected,message)
            self.assertNotIn('private-url',message)

    def test_subscription_ignores_client_routing_deeplinks(self):
        raw='vless://'+ID+'@vpn.example:443?type=tcp&security=tls#X\nincy://routing/onadd/eyJOYW1lIjoiRXhhbXBsZSJ9\nhapp://routing/onadd/eyJOYW1lIjoiRXhhbXBsZSJ9'
        for text in (raw,base64.b64encode(raw.encode()).decode()):
            profiles,native=parse_payload(text,'SUB1')
            self.assertEqual(len(profiles),1)
            self.assertEqual(native,[])
        with self.assertRaises(Invalid):
            parse_payload(raw+'\nunknown-proxy://secret@vpn.example:443','SUB1')

    def test_sources_get_separate_providers_and_shared_hook(self):
        import os,tempfile
        from unittest.mock import patch,Mock
        from pathlib import Path
        with tempfile.TemporaryDirectory() as work:
            link='vless://'+ID+'@vpn.example:443?security=tls#Same-name'
            with patch.dict(os.environ,{'WORKDIR':work,'SUB1':link,'SUB2':link,'SRV1':'tuic://user:pass@tuic.example:443#Native'},clear=True):
                b=Bridge()
                with patch('bridge.subprocess.run',return_value=Mock(returncode=0)),patch('bridge.subprocess.Popen'):
                    b.refresh()
                self.assertEqual(set(b.providers),{'SUB1','SUB2','SRV1'})
                first=json.loads(b.provider_body('SUB1'))['proxies']
                second=json.loads(b.provider_body('SUB2'))['proxies']
                self.assertEqual(len(first),1);self.assertEqual(len(second),1)
                self.assertNotEqual(first[0]['port'],second[0]['port'])
                self.assertNotEqual(first[0]['name'],second[0]['name'])
                self.assertTrue(b.provider_body('SRV1').startswith(b'tuic://'))
                hook=(Path(work)/'user_sh/jackett-all-xray.sh').read_text()
                for key in ('SUB1','SUB2','SRV1'):
                    self.assertIn('add_provider '+key+' http',hook)
                    self.assertIn('/providers/'+key,hook)
                self.assertNotIn('add_provider JACKETT_XRAY',hook)

    def test_json_not_native_yaml(self):
        _,native=parse_payload('{"outbounds":[{"protocol":"masque","settings":{"address":"vpn.example","port":443}}]}','XRAY_JSON1')
        self.assertEqual(native,[])

if __name__=='__main__': unittest.main()
