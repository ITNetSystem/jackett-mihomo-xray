FROM ghcr.io/xtls/xray-core:26.10.31@sha256:ceabeac03a89d991d2a247361825c1d1d2e9c91cd5dc010f298c7dc0c2f325c9 AS xray
FROM wiktorbgu/mihomo-mikrotik@sha256:af31f8ec3c62f6b7ddfbf04145be6d7a6336ac2b0ba22c0e273326faf4158b1b AS runtime
COPY minimize-python.py /tmp/minimize-python.py
RUN for attempt in 1 2 3 4 5; do \
      apk add --no-cache python3 py3-yaml iproute2 && break; \
      [ "$attempt" -lt 5 ] || exit 1; sleep 5; \
    done && \
    find /usr/lib/python* -type d -name __pycache__ -prune -exec rm -rf {} + && \
    rm -rf /usr/lib/python*/ensurepip /usr/lib/python*/idlelib /usr/lib/python*/turtledemo /usr/lib/python*/test && \
    python3 /tmp/minimize-python.py && rm /tmp/minimize-python.py
COPY --from=xray /usr/local/bin/xray /usr/local/bin/xray
COPY --from=xray /usr/local/share/xray/ /usr/local/share/xray/
COPY bridge.py exec-mihomo.py network.py /usr/local/lib/jackett/
COPY version-panel.js /usr/local/share/jackett-version-panel.js
COPY --chmod=0755 check-network.sh /usr/local/bin/jackett-check-network
COPY --chmod=0755 bridge-start.sh /usr/local/bin/jackett-bridge-start
LABEL io.jackett.compatible-3x-ui="3.10.2"
LABEL io.jackett.mihomo.version="1.19.33"
LABEL io.jackett.xray.version="26.10.31"
ENV PYTHONDONTWRITEBYTECODE=1
ENV XRAY_LOCATION_ASSET=/usr/local/share/xray
ENV JACKETT_MIHOMO_VERSION=1.19.33
ENV JACKETT_XRAY_VERSION=26.10.31
ENTRYPOINT ["/sbin/tini", "--", "/usr/local/bin/jackett-bridge-start"]

FROM runtime AS ui-download
RUN wget -T 60 -O /tmp/zashboard.zip https://github.com/Zephyruso/zashboard/releases/download/v3.29.1/dist.zip && \
    echo "4f16cce229e223bd07b5a3daccfbfb8bf349d7335572d412959284ab6c9bab50  /tmp/zashboard.zip" | sha256sum -c - && \
    mkdir -p /tmp/ui && unzip -q /tmp/zashboard.zip -d /tmp/ui && \
    test -f /tmp/ui/dist/index.html
FROM runtime AS with-ui
COPY --from=ui-download /tmp/ui/dist/ /usr/local/share/jackett-ui/
ENV JACKETT_BUNDLED_UI=1
LABEL io.jackett.zashboard.version="3.29.1"
