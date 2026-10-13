#!/bin/sh
set -eu
: "${WORKDIR:=/etc/mihomo}"
export WORKDIR
mkdir -p "$WORKDIR/user_sh"
# The adapter consumes SUB/SRV once; the original entrypoint must not duplicate them.
# The adapter writes one local provider hook per SUB/SRV source after validation.
# A reused test volume must not insert stale test proxies.
export JACKETT_XRAY_TEST=0
python3 /usr/local/lib/jackett/bridge.py &
bridge_pid=$!
child_pid=''
cleanup() {
    trap - TERM INT EXIT
    [ -z "$child_pid" ] || kill "$child_pid" 2>/dev/null || true
    kill "$bridge_pid" 2>/dev/null || true
    [ -z "$child_pid" ] || wait "$child_pid" 2>/dev/null || true
    wait "$bridge_pid" 2>/dev/null || true
}
trap cleanup TERM INT EXIT
ready=0
for attempt in $(seq 1 180); do
    kill -0 "$bridge_pid" 2>/dev/null || { echo 'Subscription adapter failed'; exit 1; }
    if wget -q -O /dev/null http://127.0.0.1:18890/ready 2>/dev/null; then ready=1; break; fi
    sleep 1
done
[ "$ready" = 1 ] || { echo 'Subscription adapter startup timed out'; exit 1; }
# Python exec clears source credentials only in the Mihomo child environment.
python3 /usr/local/lib/jackett/exec-mihomo.py "$@" &
child_pid=$!
while kill -0 "$bridge_pid" 2>/dev/null && kill -0 "$child_pid" 2>/dev/null; do sleep 1; done
exit 1
