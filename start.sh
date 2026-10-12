#!/bin/sh
set -eu
: "${XRAY_CONFIG:=/etc/jackett-test/xray.json}"
: "${MIHOMO_CONFIG:=/etc/jackett-test/mihomo.yaml}"
[ -r "$XRAY_CONFIG" ] && [ -r "$MIHOMO_CONFIG" ] || { echo 'Mount private xray.json and mihomo.yaml in /etc/jackett-test'; exit 64; }
/usr/local/bin/xray run -test -config "$XRAY_CONFIG" >/dev/null
/mihomo -t -f "$MIHOMO_CONFIG" >/dev/null
/usr/local/bin/xray run -config "$XRAY_CONFIG" &
xray_pid=$!
/mihomo -f "$MIHOMO_CONFIG" &
mihomo_pid=$!
cleanup() { trap - TERM INT EXIT; kill "$xray_pid" "$mihomo_pid" 2>/dev/null || true; wait "$xray_pid" 2>/dev/null || true; wait "$mihomo_pid" 2>/dev/null || true; }
trap cleanup TERM INT EXIT
while kill -0 "$xray_pid" 2>/dev/null && kill -0 "$mihomo_pid" 2>/dev/null; do sleep 1; done
exit 1
