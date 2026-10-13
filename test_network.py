import unittest
from network import policy_rules, prepare_environment

class SafetyTests(unittest.TestCase):
    def test_legacy_automatic_flags_cannot_capture_local_sockets(self):
        for mode in ['tun', 'proxy']:
            env={'JACKETT_NETWORK_MODE':mode,'TUN':'0','TUN_AUTO_ROUTE':'true','TUN_AUTO_REDIRECT':'true'}
            self.assertEqual(prepare_environment(env),mode)
            self.assertEqual(env['TUN'],'1')
            self.assertEqual(env['TUN_AUTO_ROUTE'],'false')
            self.assertEqual(env['TUN_AUTO_REDIRECT'],'false')
    def test_mode_does_not_depend_on_architecture_or_nft(self):
        for arch in ['arm','arm64','amd64']:
            env={'ARCH':arch};self.assertEqual(prepare_environment(env),'tun')
    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(ValueError):prepare_environment({'JACKETT_NETWORK_MODE':'auto'})
    def test_all_capture_rules_require_incoming_physical_interface(self):
        for ipv6 in [False,True]:
            rules=policy_rules('veth1jackett',ipv6)
            for rule in rules:self.assertEqual(rule[rule.index('iif')+1],'veth1jackett')
            self.assertEqual(rules[-1][-1],'2022')
            self.assertTrue(all('main' in rule for rule in rules[:-1]))
