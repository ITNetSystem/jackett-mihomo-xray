# Jackett Mihomo + Xray для MikroTik

Образ: **`ghcr.io/itnetsystem/jackett-mihomo-xray:latest`**.
Дополнительный образ: **`ghcr.io/itnetsystem/jackett-mihomo-xray:with-ui`** — со встроенным Zashboard 3.29.1, без загрузки GUI при запуске. Поддерживает те же архитектуры, ENV и протоколы. Он больше на размер встроенного интерфейса.

Имя контейнера: **`jackett-mihomo-xray`**.

Полная сборка: Mihomo 1.19.33 + Xray 26.10.21, ARMv7 (32-bit), ARM64 и AMD64. Версии обоих ядер отображаются в Zashboard. Сохранены SELECTOR, MANUAL, AUTO, FALLBACK, LOADBALANCE, протоколы обоих ядер и базы Xray GeoIP/GeoSite. Ручное обновление provider сразу перечитывает исходную подписку, а выбранный режим и узел MANUAL сохраняются после перезапуска контейнера.

**[Пошаговая инструкция](README-BRIDGE.md)** — сеть, ENV, установка, обновление и удаление.

## Настройка через ENV

SUB1, SUB2, SUB3 и далее — URL подписок. SRV1, SRV2 и далее — отдельные ссылки, включая WireGuard и SOCKS5. Источники показываются отдельными провайдерами; общие группы включают их все. UI_SECRET необязателен. Подробности SUB_USER_AGENT, HWID и форматов — в инструкции.

После подготовки свободного интерфейса и ENV:

```routeros
/container/add name=jackett-mihomo-xray remote-image=ghcr.io/itnetsystem/jackett-mihomo-xray:latest envlists=jackett interface=veth1jackett root-dir=containers/jackett dns=1.1.1.1 logging=yes start-on-boot=no
```

После загрузки:

```routeros
/container/start [/container/find where name=jackett-mihomo-xray]
```

RouterOS создаёт папку сам. Отдельные config/tmp, mountlists и xray.json для обычной подписки не нужны. Используйте существующий мост `Docker Bridge`, список ENV `jackett`; не назначайте IP/интерфейс, занятые другим контейнером.

## Порты

- **1080 — общий HTTP/SOCKS прокси**, включая поддерживаемую SOCKS5 UDP-передачу.
- **9090 — API и GUI**.
- **53 — DNS Mihomo**, если DNS_ENABLE включён.

GUI: `http://172.31.203.4:9090/ui/#/setup?hostname=172.31.203.4&port=9090&secret=` — замените IP своим, при UI_SECRET заполните Secret. Прозрачная маршрутизация LAN настраивается отдельно на MikroTik.

## Размер и хранилище

Ориентировочный размер файловой системы — **160 МиБ**; размер зависит от архитектуры и версии сборки. Стандартная библиотека Python упакована в ZIP; Mihomo, Xray и Geo-базы сохранены. GUI скачивается дополнительно, временная распаковка тоже требует места.

Используйте постоянный накопитель с запасом места для образа, распаковки, конфигураций и веб-панели.

## Сеть

Единый режим TUN на всех поддерживаемых архитектурах. В TUN направляются только пакеты, пришедшие от RouterOS. Исходящие соединения Xray и управление контейнером используют обычный шлюз, без повторного перехвата. `TUN_AUTO_ROUTE` и `TUN_AUTO_REDIRECT` принудительно отключены. Для явного HTTP/SOCKS без TUN задайте `JACKETT_NETWORK_MODE=proxy`.

[Настройка сети и безопасное обновление](README-BRIDGE.md#как-работает-сеть).
