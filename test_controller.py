import tempfile
import unittest
from unittest.mock import Mock

from controller import Controller, country_for, flag_for


class ControllerTests(unittest.TestCase):
    def controller(self, mode='auto', selected='node-20000'):
        c=Controller.__new__(Controller)
        c.state={'mode':mode,'selected':selected}
        c.bridge=Mock()
        c.bridge.proxies=[
            {'name':'[Xray] Serbia','port':20000},
            {'name':'[Xray] Estonia','port':20001},
        ]
        return c

    def test_router_is_xray_only_with_native_tun(self):
        config=self.controller().build_router_config()
        self.assertEqual(config['inbounds'][0]['protocol'],'tun')
        self.assertEqual(config['inbounds'][0]['settings']['name'],'xray0')
        self.assertEqual(config['inbounds'][0]['settings']['autoSystemRoutingTable'],[])
        self.assertEqual({x['protocol'] for x in config['outbounds']},{'socks','freedom','blackhole'})
        self.assertNotIn('mihomo',str(config).lower())

    def test_modes_map_to_xray_routing(self):
        manual=self.controller('manual').build_router_config()['routing']
        self.assertEqual(manual['rules'][0]['outboundTag'],'node-20000')
        auto=self.controller('auto').build_router_config()['routing']
        self.assertEqual(auto['balancers'][0]['strategy']['type'],'leastping')
        fallback=self.controller('fallback').build_router_config()['routing']
        self.assertEqual(fallback['balancers'][0]['strategy']['type'],'leastload')
        self.assertEqual(fallback['balancers'][0]['fallbackTag'],'node-20000')

    def test_unknown_selected_node_is_repaired(self):
        c=self.controller(selected='missing')
        self.assertEqual(c._selected(),'node-20000')

    def test_country_is_derived_from_code_or_name(self):
        self.assertEqual(country_for('RS Сербия - TCP'),('RS','Сербия'))
        self.assertEqual(country_for('Estonia XHTTP'),('EE','Эстония'))
        self.assertEqual(country_for('Custom node'),('','Локация'))
        self.assertEqual(flag_for('RO'),'🇷🇴')
        nodes=self.controller().nodes()
        self.assertEqual(nodes[0]['countryCode'],'RS')
        self.assertEqual(nodes[1]['flag'],'🇪🇪')

    def test_connection_probe_uses_node_socks_listener(self):
        from unittest.mock import patch
        class Connection:
            def __init__(self): self.data=bytearray(b'\x05\x00\x05\x00\x00\x01\x7f\x00\x00\x01\x01\xbb')
            def __enter__(self): return self
            def __exit__(self,*_): pass
            def settimeout(self,_): pass
            def sendall(self,_): pass
            def recv(self,length):
                result=self.data[:length];del self.data[:length];return bytes(result)
        c=self.controller()
        with patch('controller.socket.create_connection',return_value=Connection()) as connect:
            result=c.probe_node(c.nodes()[0])
        self.assertTrue(result['ok'])
        connect.assert_called_once_with(('127.0.0.1',20000),timeout=8)


if __name__=='__main__': unittest.main()
