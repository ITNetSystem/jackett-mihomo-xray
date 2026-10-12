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
