> **АРХИВ.** Это описание старых образов. Для текущей сборки используйте [главную инструкцию](README.md).

# Experimental Mihomo + Xray for MikroTik

Mihomo 1.19.32 plus Xray 26.10.10, ARM64 and AMD64. Xray provides MASQUE/XDRIVE; Mihomo selects local SOCKS proxies. This is a separate experimental container, not a replacement for a working production container.

No customer credentials, subscription URLs or server certificates are included. Mount your private xray.json and mihomo.yaml under /etc/jackett-test. The image stops if either process exits.

## Publishing

Push this directory to the main branch, or run the Publish workflow. GitHub Actions uses its built-in GITHUB_TOKEN with packages:write; no personal token needs to be placed in repository files. Workflow files must be enabled/authorized for this repository.

After the first successful publication set the package visibility to Public in GitHub Packages settings if anonymous pulling is required. Public repository visibility alone does not make the new GHCR package public.

## MikroTik installation

For repository ITNetSystem/jackett-mihomo-xray, after image publication and public visibility, use the following single line. It assumes the test veth, configuration mount and usb1 disk already exist:

```routeros
/container/config/set registry-url=https://ghcr.io; /container/add remote-image=itnetsystem/jackett-mihomo-xray:1.19.32-xray26.10.10 interface=veth-aportnov-test root-dir=usb1/jackett-aportnov-root mounts=aportnov-test-config logging=yes start-on-boot=no
```

Changing registry-url also changes the default registry for future container pulls. Existing containers keep running. Start the new container only after extraction completes. Do not stop the old one during initial testing.

The new router needs outbound access to the test server ports: TCP 8450 (MASQUE HTTP/2) and TCP 8451 (XDRIVE HTTPS storage). The subscription-only VM does not need these ports in normal operation.

Image version tag is explicit; do not replace production with an automatically changing latest image.

## Verification status

MASQUE and XDRIVE both passed HTTPS 204 tests through Mihomo on AMD64 from VPN1 to VPN2. ARM64 image builds successfully; native RouterOS runtime has not yet been verified.

## References

- https://manual.mikrotik.com/docs/containers/
- https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry
- https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images

## Environment variables

Currently supported: XRAY_CONFIG and MIHOMO_CONFIG (paths to mounted configuration files). LOG_LEVEL, EXTERNAL_UI_URL, SUB1, SRV1 and SRV2 from third-party MikroTik wrappers are not automatically interpreted by this image. Providers, UI and log level must be specified in mihomo.yaml. Do not treat this image as a drop-in replacement for such wrappers until their initialization behavior is ported and tested.

## MikroTik wrapper-compatible variant

Use tag `mikrotik-xray26.10.10` for the MikroTik-compatible variant. It inherits the complete original wiktorbgu/mihomo-mikrotik image at the fixed digest `sha256:3140540997abafa6bc649ae0cebb42b0e3ffbec9eb1d3cd601edde9d355eb733`, including the original entrypoint, templates, ENV defaults, TUN setup, subscription processing and UI. The upstream binaries and template semantics are retained; this variant is distinct from the minimal image described above.

`SUB1`, `SUB2`, `SRV1`, `SRV2`, `EXTERNAL_UI_URL`, `LOG_LEVEL` and other upstream ENV settings remain handled by the original entrypoint/templates. Existing disabled RouterOS ENV entries remain disabled. Existing customized configurations still determine which ENV/template features apply.

By default Xray is disabled and the upstream entrypoint runs unchanged. For the separate test set `JACKETT_XRAY_TEST=1` and mount private `xray.json` at `/etc/jackett-test/xray.json`. The original template user_sh hook adds the two local SOCKS test proxies to the file provider `JACKETT_XRAY_TEST`. Custom templates must use PROVIDERS_BLOCK/PROVIDERS_LIST for those extra proxies to appear. The default group can auto-select these test proxies when enabled; use a separate container and separate writable /etc/mihomo mount, never the production container's directory.

For this variant the upstream mixed proxy port defaults to **1080** (minimal image uses 7890); UI/API defaults to **9090**. Normal ENV subscriptions do not require the test Xray mount when JACKETT_XRAY_TEST is unset. Preserve the existing API secret/HWID and mounts when migrating; changing storage may generate a new HWID.

After publication, with a prepared separate veth/mount and an ENV list named mihomo-test:

```routeros
/container/config/set registry-url=https://ghcr.io; /container/add remote-image=itnetsystem/jackett-mihomo-xray:mikrotik-xray26.10.10 envlists=mihomo-test interface=veth-aportnov-test root-dir=usb1/jackett-aportnov-root mounts=aportnov-test-config logging=yes start-on-boot=no
```

The ENV list should be copied for testing, not edited on the running production container. Make sure the MikroTik test interface uses ordinary WAN routing so it does not loop back into the current proxy.

## Новый мост подписок через ENV

Для передачи обычных SUB/SRV подключений в Xray используйте отдельный тег `mikrotik-all-xray26.10.10-v1`. Настройка через ENV без приватного xray.json, правила форматов, команды для RB5009 и проверки описаны в [README-BRIDGE.md](README-BRIDGE.md). Прежний `mikrotik-xray26.10.10` обслуживает через Xray только два тестовых протокола; это разные сборки.
