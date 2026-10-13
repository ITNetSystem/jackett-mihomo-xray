import unittest, tempfile, os, json
from unittest.mock import patch,Mock
from pathlib import Path
from compact import Controller
from bridge import Invalid

class CompactTests(unittest.TestCase):
    def test_selection_provider_and_persistence(self):
        with tempfile.TemporaryDirectory() as work:
            profiles=json.dumps([{'remarks':name,'outbounds':[{'protocol':'freedom','tag':'proxy'}]} for name in ('One','Two')])
            with patch.dict(os.environ,{'WORKDIR':work,'SUB1':profiles},clear=True),patch('bridge.subprocess.run',return_value=Mock(returncode=0)),patch('bridge.subprocess.Popen'):
                c=Controller();c.refresh()
                nodes=c.providers_body()['providers']['SUB1']['proxies']
                self.assertEqual(len(nodes),2)
                c.activate(nodes[1]['name'])
                self.assertEqual(c.proxies_body()['proxies']['SELECTOR']['now'],nodes[1]['name'])
                cfg=json.loads((c.state/'selected-config.json').read_text())
                self.assertEqual([(x['protocol'],x['port']) for x in cfg['inbounds']],[('socks',1080),('http',1081)])
                self.assertEqual(json.loads((Path(work)/'selected.json').read_text()),nodes[1]['name'])
                with self.assertRaises(Invalid):c.activate('unknown')
                other=Controller();other.refresh();self.assertEqual(other.selected,nodes[1]['name'])
    def test_native_mihomo_protocol_is_rejected(self):
        with tempfile.TemporaryDirectory() as work,patch.dict(os.environ,{'WORKDIR':work,'SRV1':'tuic://u:p@vpn.example:443#T'},clear=True):
            c=Controller()
            with self.assertRaises(Invalid):c.fetch('SRV1',c.sources['SRV1'])
            with self.assertRaises(Invalid):c.refresh()

if __name__=='__main__':unittest.main()
