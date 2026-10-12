#!/bin/sh
# Keep the original MikroTik environment/template initialization intact.
if [ "${JACKETT_XRAY_TEST:-0}" != 1 ]; then
    exec /entrypoint.sh "$@"
fi
set -eu
: "${XRAY_CONFIG:=/etc/jackett-test/xray.json}"
: "${WORKDIR:=/etc/mihomo}"
[ -r "$XRAY_CONFIG" ] || { echo 'Missing private Xray test config' >&2; exit 64; }
/usr/local/bin/xray run -test -config "$XRAY_CONFIG" >/dev/null || { echo 'Invalid Xray test config' >&2; exit 65; }
mkdir -p "$WORKDIR/user_sh"
# Original entrypoint sources user_sh before rendering its provider template.
cat > "$WORKDIR/user_sh/jackett-xray-test.sh" <<'HOOK'
if [ "${JACKETT_XRAY_TEST:-0}" = 1 ]; then
cat > "$WORKDIR/jackett-xray-test.yaml" <<'PROXIES'
proxies:
  - name: TEST MASQUE - Estonia
    type: socks5
    server: 127.0.0.1
    port: 10850
    udp: true
  - name: TEST XDRIVE - Estonia
    type: socks5
    server: 127.0.0.1
    port: 10851
    udp: true
PROXIES
add_provider JACKETT_XRAY_TEST file "$WORKDIR/jackett-xray-test.yaml" false
fi
HOOK
/usr/local/bin/xray run -config "$XRAY_CONFIG" &
xray_pid=$!
/entrypoint.sh "$@" &
mihomo_pid=$!
cleanup() { trap - TERM INT EXIT; kill "$xray_pid" "$mihomo_pid" 2>/dev/null || true; wait "$xray_pid" 2>/dev/null || true; wait "$mihomo_pid" 2>/dev/null || true; }
trap cleanup TERM INT EXIT
while kill -0 "$xray_pid" 2>/dev/null && kill -0 "$mihomo_pid" 2>/dev/null; do sleep 1; done
exit 1
