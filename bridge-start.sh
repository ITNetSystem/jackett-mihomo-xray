#!/bin/sh
set -eu
: "${PATH:=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}"
export PATH
: "${WORKDIR:=/etc/mihomo}"
export WORKDIR
# Force one network mode on every architecture; never let TUN capture Xray sockets.
export JACKETT_NETWORK_MODE="${JACKETT_NETWORK_MODE:-tun}"
case "$JACKETT_NETWORK_MODE" in tun|proxy) ;; *) echo 'Invalid network mode'; exit 1;; esac
export TUN=1 TUN_AUTO_ROUTE=false TUN_AUTO_REDIRECT=false
# The selected top-level mode and MANUAL node are runtime state. Persist them
# even when an old RouterOS ENV list still contains STORE_SELECTED=false.
export STORE_SELECTED=true
mkdir -p "$WORKDIR/user_sh"
case "${EXTERNAL_UI_PATH:-ui}" in
    /*) ui_dir="${EXTERNAL_UI_PATH}" ;;
    *) ui_dir="$WORKDIR/${EXTERNAL_UI_PATH:-ui}" ;;
esac
if [ "${JACKETT_BUNDLED_UI:-0}" = 1 ]; then
    mkdir -p "$ui_dir"
    cp -R /usr/local/share/jackett-ui/. "$ui_dir/"
    echo 'Bundled Zashboard ready; no startup download required'
fi

# The upstream dashboard only reports the Mihomo API version. Add a small,
# non-interactive badge after either the bundled or downloaded UI is ready so
# operators can also see which Xray core serves the [Xray] connections.
install_version_panel() {
    for _ in $(seq 1 180); do
        [ -f "$ui_dir/index.html" ] && break
        sleep 1
    done
    [ -f "$ui_dir/index.html" ] || return 0
    cp /usr/local/share/jackett-version-panel.js "$ui_dir/jackett-versions.js"
    if ! grep -q 'jackett-versions.js' "$ui_dir/index.html"; then
        sed -i 's#</body>#<script src="./jackett-versions.js"></script></body>#' "$ui_dir/index.html"
    fi
    echo "Version badge ready: Mihomo ${JACKETT_MIHOMO_VERSION:-unknown} · Xray ${JACKETT_XRAY_VERSION:-unknown}"
}
install_version_panel &
version_panel_pid=$!

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
    kill "$version_panel_pid" 2>/dev/null || true
    [ -z "$child_pid" ] || wait "$child_pid" 2>/dev/null || true
    wait "$bridge_pid" 2>/dev/null || true
    wait "$version_panel_pid" 2>/dev/null || true
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
python3 /usr/local/lib/jackett/network.py || { echo 'Safe network setup failed'; exit 1; }
while kill -0 "$bridge_pid" 2>/dev/null && kill -0 "$child_pid" 2>/dev/null; do sleep 1; done
exit 1
