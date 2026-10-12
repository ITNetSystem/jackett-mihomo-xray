FROM ghcr.io/xtls/xray-core:26.10.10@sha256:ac00cba4be8f428fc65c8c9a4e4c8fa55e3f6270d8a8d54316100ff3946899ce AS xray
FROM metacubex/mihomo:v1.19.32
COPY --from=xray /usr/local/bin/xray /usr/local/bin/xray
COPY --chmod=0755 start.sh /usr/local/bin/jackett-test-start
ENV XRAY_CONFIG=/etc/jackett-test/xray.json
ENV MIHOMO_CONFIG=/etc/jackett-test/mihomo.yaml
ENTRYPOINT ["/bin/sh", "/usr/local/bin/jackett-test-start"]
