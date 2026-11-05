#!/bin/sh
set -eu
: "${PATH:=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}"
export PATH
: "${WORKDIR:=/etc/mihomo}"
export WORKDIR
export JACKETT_NETWORK_MODE="${JACKETT_NETWORK_MODE:-tun}"
case "$JACKETT_NETWORK_MODE" in tun|proxy) ;; *) echo 'Invalid network mode'; exit 1;; esac
mkdir -p "$WORKDIR"

python3 /usr/local/lib/jackett/controller.py &
controller_pid=$!
cleanup() {
    trap - TERM INT EXIT
    kill "$controller_pid" 2>/dev/null || true
    wait "$controller_pid" 2>/dev/null || true
}
trap cleanup TERM INT EXIT

ready=0
for attempt in $(seq 1 180); do
    kill -0 "$controller_pid" 2>/dev/null || { echo 'VPN Jackett controller failed'; exit 1; }
    if wget -q -O /dev/null http://127.0.0.1:9090/api/ready 2>/dev/null; then ready=1; break; fi
    sleep 1
done
[ "$ready" = 1 ] || { echo 'VPN Jackett controller startup timed out'; exit 1; }
wait "$controller_pid"
