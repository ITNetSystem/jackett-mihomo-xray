#!/bin/sh
set -eu
mkdir -p /tmp/check-network
cat > /tmp/check-network/default_config.yaml <<'YAML'
listeners:
- name: tun-in
  type: tun
  device: Meta
  auto-route: false
  auto-redirect: false
YAML
ip link add Meta type dummy
ip link set Meta up
WORKDIR=/tmp/check-network JACKETT_NETWORK_MODE=tun python3 /usr/local/lib/jackett/network.py
iface=$(ip -j -4 route show default | python3 -c 'import json,sys;print(json.load(sys.stdin)[0]["dev"])')
ip route get 8.8.8.8 | grep "dev $iface"
ip route get 8.8.8.8 from 198.51.100.2 iif "$iface" | grep 'dev Meta'
ip route get 10.20.108.1 from 198.51.100.2 iif "$iface" | grep "dev $iface"
local_ip=$(ip -j -4 addr show dev "$iface" | python3 -c 'import json,sys;print(json.load(sys.stdin)[0]["addr_info"][0]["local"])')
ip route get "$local_ip" from 198.51.100.2 iif "$iface" | grep 'local'
echo 'PASS: forwarded traffic captured; Xray/subscriptions and management bypass TUN'
