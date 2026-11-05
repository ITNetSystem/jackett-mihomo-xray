import tempfile
import unittest
from unittest.mock import Mock

from controller import Controller, Invalid


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


if __name__=='__main__': unittest.main()
