FROM ghcr.io/xtls/xray-core:26.10.31@sha256:ceabeac03a89d991d2a247361825c1d1d2e9c91cd5dc010f298c7dc0c2f325c9 AS xray
FROM alpine:3.22@sha256:2e0b81d60597f449baa56dc25d355367869d2dca4cd57e866f1e2b52af3eb55f AS runtime
RUN for attempt in 1 2 3 4 5; do \
      apk add --no-cache python3 tini iproute2 ca-certificates && break; \
      [ "$attempt" -lt 5 ] || exit 1; sleep 5; \
    done && \
    find /usr/lib/python* -type d -name __pycache__ -prune -exec rm -rf {} + && \
    rm -rf /usr/lib/python*/ensurepip /usr/lib/python*/idlelib /usr/lib/python*/turtledemo /usr/lib/python*/test
COPY --from=xray /usr/local/bin/xray /usr/local/bin/xray
COPY --from=xray /usr/local/share/xray/ /usr/local/share/xray/
COPY bridge.py controller.py network.py /usr/local/lib/jackett/
COPY ui/ /usr/local/share/jackett-ui/
COPY --chmod=0755 check-network.sh /usr/local/bin/jackett-check-network
COPY --chmod=0755 bridge-start.sh /usr/local/bin/jackett-bridge-start
LABEL io.jackett.compatible-3x-ui="3.11.0"
LABEL io.jackett.xray.version="26.10.31"
LABEL org.opencontainers.image.title="VPN Jackett Xray"
ENV PYTHONDONTWRITEBYTECODE=1
ENV XRAY_LOCATION_ASSET=/usr/local/share/xray
ENV JACKETT_XRAY_VERSION=26.10.31
ENV WORKDIR=/etc/mihomo
EXPOSE 1080 1081 9090
ENTRYPOINT ["/sbin/tini", "--", "/usr/local/bin/jackett-bridge-start"]
