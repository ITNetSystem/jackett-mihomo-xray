# Jackett Compact — Xray и Zashboard для MikroTik

Отдельный образ: `ghcr.io/itnetsystem/jackett-mihomo-xray:mikrotik-compact-xray26.10.10-v1`.
ARM64 (включая hAP ax²) и AMD64. Xray 26.10.10; Mihomo и встроенных Geo-баз нет.

Измеренный размер чистой файловой системы AMD64 — около **76 МиБ**. Zashboard скачивается при запуске и занимает дополнительно около 8 МиБ. Файлы подписок, кэш и временная распаковка тоже требуют места. Установка на hAP ax² зависит от фактического `free-hdd-space`; наличие накопителя 128 МБ само по себе не гарантирует свободные 84+ МиБ. Для загрузки можно использовать tmpdir на RAM-диске, root-dir оставить на постоянном накопителе.

## Возможности и ограничения

- SUB1, SUB2, SUB3 и далее: URL подписок; SRV1, SRV2: отдельные ссылки.
- WireGuard, VLESS, VMess, Trojan, Shadowsocks, Hysteria2 и остальные профили, которые поддерживает преобразователь Xray. TCP, gRPC, XHTTP и другие поддерживаемые Xray транспорты сохраняются.
- Отдельные провайдеры, ручной выбор в SELECTOR, тест задержки через локальный SOCKS конкретного узла, обновление подписок и сохранение выбора.
- GUI Zashboard использует базовые совместимые API. Это не полная реализация Mihomo: графики трафика, журнал WebSocket, список соединений, AUTO, балансировка, TUN и редактор маршрутизации через GUI не реализованы. Неподдерживаемые запросы возвращают ошибку, а не вымышленные показатели.
- Протоколы, которые обслуживало только Mihomo (например TUIC/AnyTLS/SSR), в этой сборке недоступны. Источник с такими записями отключается с сообщением в журнале. Для них используйте полную сборку.
- Базы GeoIP/GeoSite исключены. Полный JSON с `geoip:`/`geosite:` без файлов баз не пройдёт проверку Xray.
- При смене выбранного подключения публичный процесс Xray перезапускается; текущие соединения прерываются. Обновление неизменённого выбранного профиля не перезапускает его.
- Один Xray-процесс на профиль для проверки задержек, плюс процесс выбранного узла. Меньший размер на диске не означает минимального потребления RAM при большом числе узлов.

## Чистая установка

Пример сети: bridge `Docker Bridge`, контейнер `172.31.203.4/24`, шлюз `172.31.203.254`. Подставьте вашу сеть. **IP и интерфейс должны быть свободны**; команды создания интерфейса не выполняйте повторно для уже работающего контейнера.

```routeros
/interface/veth/add name=veth4jackett address=172.31.203.4/24 gateway=172.31.203.254
/interface/bridge/port/add bridge="Docker Bridge" interface=veth4jackett
/container/envs/add list=jackett key=SUB1 value="ВАША_ССЫЛКА_ПОДПИСКИ"
/container/envs/add list=jackett key=PROVIDER_INTERVAL value=3600
/container/envs/add list=jackett key=EXTERNAL_UI_URL value="https://github.com/Zephyruso/zashboard/releases/latest/download/dist-cdn-fonts.zip"
/container/add name=jackett-xray-compact remote-image=ghcr.io/itnetsystem/jackett-mihomo-xray:mikrotik-compact-xray26.10.10-v1 envlists=jackett interface=veth4jackett root-dir=containers/jackett-compact dns=1.1.1.1 logging=yes start-on-boot=yes
```

После загрузки:

```routeros
/container/start [/container/find where name=jackett-xray-compact]
```

Настройте NAT/маршруты/firewall для своей контейнерной сети. Контейнер сам не меняет правила MikroTik. `SUB_USER_AGENT`, `HWID` и поведение SUB/SRV такие же, как у полной версии. Старые ENV Mihomo вроде `TUN_*`, `DNS_*`, `PROVIDERS_BLOCK`, `CONFIG` не настраивают compact; это отдельный контроллер.

## Порты и интерфейс

- `9090` — GUI и API (`UI_PORT`).
- `1080` — **SOCKS5**, включая UDP (`MIXED_PORT`, имя сохранено для привычного ENV).
- `1081` — отдельный HTTP-прокси (`HTTP_PORT`). **1080 не является смешанным HTTP/SOCKS портом в compact.**
- DNS-сервер на порту 53 этой сборкой не предоставляется. Если ваши клиенты использовали DNS Mihomo, настройте другой DNS до перехода.

Откройте `http://172.31.203.4:9090/ui/#/setup?hostname=172.31.203.4&port=9090&secret=`.
`UI_SECRET` необязателен. При его установке впишите значение в поле Secret интерфейса; доступность API и прокси ограничивайте своей доверенной сетью.

В SELECTOR выберите узел. Режим — GLOBAL; клиентские правила из конфигураций Xray сохраняются, редактор правил Mihomo не действует.

## RAM для временной установки

Для RouterOS с tmpfs и достаточной свободной RAM:

```routeros
/disk/add type=tmpfs slot=container-tmp tmpfs-max-size=128M
/container/config/set tmpdir=container-tmp
```

Не создавайте диск повторно, если он уже есть. Предел 128 МБ ограничивает расход RAM; сам контейнер здесь не хранится. После перезагрузки временные данные очищаются. Для возврата прежнего стандартного tmpdir: `/container/config/set tmpdir=""`.

## Обновление

```routeros
/container/stop [/container/find where name=jackett-xray-compact]
/container/repull [/container/find where name=jackett-xray-compact]
```

Дождитесь завершения загрузки, затем запустите контейнер. Не переключайте работающий полный контейнер на compact до проверки зависимостей HTTP/SOCKS/DNS и свободного места; для испытания используйте отдельный свободный интерфейс и IP.

## Что происходит при переключении узла

SELECTOR меняет выбранный профиль публичного Xray и перезапускает этот процесс. Уже открытые TCP-соединения и UDP-сессии прекращаются: браузер и приложения обычно переподключаются, но звонок или загрузка файла могут прерваться. Новые соединения используют выбранный узел. Обновление подписки без изменения выбранного профиля не перезапускает этот процесс. Это ограничение текущей compact-реализации, а не обязательное свойство Xray.
