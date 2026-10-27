# Полная сборка Mihomo + Xray — установка на MikroTik

Образ: `ghcr.io/itnetsystem/jackett-mihomo-xray:latest`.
Mihomo 1.19.33 + Xray 26.10.21. Архитектуры ARMv7 (32-bit), ARM64 и AMD64. Версии обоих ядер показаны значком в Zashboard.

Подключения добавляются через ENV. SUB1/SUB2 содержат адреса подписок, SRV1/SRV2 — отдельные ссылки. Источники отображаются отдельными провайдерами SUB1, SUB2, SRV1, SRV2 и обновляются автоматически; общая группа SELECTOR включает их все. Файлы конфигурации для обычной подписки создаются контейнером.

## Порядок установки

1. [Подготовьте RouterOS и накопитель](#1-подготовка-routeros-и-хранилища).
2. [Подключите сеть контейнера](#2-сеть-контейнера).
3. [Добавьте подписку в ENV](#3-env-подписка-и-веб-панель).
4. [Загрузите и запустите образ](#4-загрузка-и-запуск).
5. [Откройте веб-панель](#5-веб-панель-и-подключение).

Дополнительно: [сеть](#как-работает-сеть), [ENV](#справочник-env), [протоколы](#протоколы-и-форматы), [обновление](#обновление-образа), [удаление](#удаление-контейнера).

В примерах: контейнер `jackett-mihomo-xray`, интерфейс `veth1jackett`, ENV-список `jackett`, папка `containers/jackett`. IP и шлюз — примеры: подставьте свою сеть, не меняйте работающие адреса.

## Что означают list, key и value

В команде `/container/envs/add list=jackett key=SUB1 value="ВАША_ПОДПИСКА"`:

- `list=jackett` — имя набора переменных для контейнера;
- `key=SUB1` — имя переменной;
- `value` — её значение, здесь адрес подписки;
- `envlists=jackett` при установке подключает весь этот набор к контейнеру.

`jackett` — имя списка, а не отдельный параметр ядра. Один список может содержать SUB1, SUB2, SRV1, SRV2 и настройки панели одновременно.

## 1. Подготовка RouterOS и хранилища

Нужны RouterOS 7 с пакетом container соответствующей архитектуры и включённым режимом container. Проверьте:

```routeros
/system/resource/print
/system/package/print
/system/device-mode/print
/disk/print
```

Если container отключён:

```routeros
/system/device-mode/update container=yes
```

Подтвердите изменение физически способом, указанным RouterOS. Файлы образа, конфигурация, кеш и HWID хранятся внутри одного root-dir — **containers/jackett**. RouterOS создаёт каталог при распаковке образа. Команды /file/add и отдельный mount не нужны. При новой установке этот путь должен быть свободен.

```routeros
/container/config/set registry-url=https://ghcr.io tmpdir=""
```

Пустой tmpdir возвращает автоматический выбор каталога распаковки. Это общая настройка загрузки контейнеров; другие запущенные контейнеры не меняются.

## 2. Сеть контейнера

Используется мост **Docker Bridge** и интерфейс **veth1jackett**. Если они уже созданы, не создавайте повторно и сохраните их действующие IP/шлюз. Посмотрите текущую сеть:

```routeros
/interface/bridge/print where name="Docker Bridge"
/ip/address/print where interface="Docker Bridge"
/interface/veth/print detail where name=veth1jackett
/interface/bridge/port/print where interface=veth1jackett
```

В командах используется сеть **172.31.203.0/24**: шлюз 172.31.203.254, контейнер 172.31.203.4. Если Docker Bridge уже обслуживает другую сеть, используйте свободный адрес из неё и существующий шлюз; замените адреса в командах NAT/firewall и URL панели. Команды создания выполняйте только для отсутствующих элементов:

```routeros
/interface/bridge/add name="Docker Bridge"
/ip/address/add address=172.31.203.254/24 interface="Docker Bridge"
/interface/veth/add name=veth1jackett address=172.31.203.4/24 gateway=172.31.203.254
/interface/bridge/port/add bridge="Docker Bridge" interface=veth1jackett
/ip/firewall/nat/add chain=srcnat src-address=172.31.203.0/24 out-interface-list=WAN action=masquerade comment="Jackett container Internet"
```

В примере WAN — существующий список внешних интерфейсов. Если его нет, в правиле NAT замените `out-interface-list=WAN` на `out-interface=ИМЯ_ВАШЕГО_WAN`. Контейнер должен выходить в интернет обычным маршрутом; не направляйте его собственный трафик обратно через него.

При блокирующих правилах forward разрешите трафик контейнера в WAN, ответный established/related и доступ из доверенной LAN к TCP 1080/9090. Разрешения должны стоять перед блокирующими правилами. Например, если у вас настроены списки LAN и WAN:

```routeros
/ip/firewall/filter/add chain=forward action=accept dst-address=172.31.203.4 connection-state=established,related place-before=0 comment="Jackett return traffic"
/ip/firewall/filter/add chain=forward action=accept src-address=172.31.203.4 out-interface-list=WAN place-before=0 comment="Jackett outbound"
/ip/firewall/filter/add chain=forward action=accept in-interface-list=LAN dst-address=172.31.203.4 protocol=tcp dst-port=1080,9090 place-before=0 comment="Jackett LAN access"
```

Эти правила не отменяют блокировку в RAW или внешнем firewall. Публиковать API 9090 в интернет не требуется.

## 3. ENV: подписка и веб-панель

Замените значение подписки своим. SUB1 достаточно для запуска; остальные источники добавляются при необходимости. **UI_SECRET — необязательный параметр.** Если его не задавать или оставить пустым, API и веб-панель работают без пароля.

```routeros
/container/envs/add list=jackett key=SUB1 value="ВАША_ССЫЛКА_ПОДПИСКИ"
/container/envs/add list=jackett key=LOG_LEVEL value=info
/container/envs/add list=jackett key=EXTERNAL_UI_URL value="https://github.com/Zephyruso/zashboard/releases/latest/download/dist.zip"
/container/envs/add list=jackett key=PROVIDER_INTERVAL value=3600
```

Если нужен пароль API, добавьте отдельно:

```routeros
/container/envs/add list=jackett key=UI_SECRET value="ВАШ_ПАРОЛЬ_API"
```

Необязательные дополнительные источники:

```routeros
/container/envs/add list=jackett key=SUB2 value="ВТОРАЯ_ССЫЛКА_ПОДПИСКИ"
/container/envs/add list=jackett key=SRV1 value="ССЫЛКА_ПОДКЛЮЧЕНИЯ_1"
/container/envs/add list=jackett key=SRV2 value="ССЫЛКА_ПОДКЛЮЧЕНИЯ_2"
```

Не добавляйте строки с заполнителями без замены значений. Не повторяйте один источник в SUB и SRV без необходимости. Для изменения существующей переменной:

```routeros
/container/envs/set [/container/envs/find where list=jackett and key=SUB1] value="НОВАЯ_ССЫЛКА_ПОДПИСКИ"
```

После изменения ENV перезапустите контейнер; содержимое подписки обновляется автоматически, без перезапуска.

### WireGuard отдельной ссылкой

WireGuard работает через пользовательский сетевой стек Xray, без отдельного TUN-интерфейса и прав администратора контейнера. Параметр `dns` задаёт DNS внутри туннеля; UDP до WireGuard-сервера должен быть разрешён.

Готовую ссылку `wireguard://…` или `wg://…` вставьте целиком в `SRV1` или `SRV2`. Символы `+`, `/` и `=` внутри PrivateKey, PublicKey и PresharedKey заменять вручную не нужно. Уже закодированные ссылки с `%2B`, `%2F`, `%3D` также принимаются без изменений.

```routeros
/container/envs/add list=jackett key=SRV1 value="wireguard://PRIVATE_KEY@SERVER:51820?address=10.7.0.2/32&publickey=SERVER_PUBLIC_KEY&allowedips=0.0.0.0/0&keepalive=25#WireGuard"
```

Это пример структуры: замените PRIVATE_KEY, SERVER и SERVER_PUBLIC_KEY значениями своего подключения. Готовую ссылку изменять не требуется. Файл `.conf` с разделами Interface/Peer не является ссылкой и напрямую в SRV не принимается.

## 4. Загрузка и запуск

После подготовки сети и ENV создайте контейнер. Автозапуск включите после проверки:

```routeros
/container/add name=jackett-mihomo-xray remote-image=ghcr.io/itnetsystem/jackett-mihomo-xray:latest envlists=jackett interface=veth1jackett root-dir=containers/jackett dns=1.1.1.1 logging=yes start-on-boot=no
```

Дождитесь завершения downloading/extracting:

```routeros
/container/print detail
/container/start [/container/find where interface=veth1jackett]
```

В команде используется envlists=jackett. Mountlist этой установке не нужен.

## 5. Веб-панель и подключение

Откройте `http://172.31.203.4:9090/ui/`. Укажите hostname **172.31.203.4**, port **9090**, secret — значение UI_SECRET; если пароль не задавали, оставьте поле secret пустым. Если нужна страница настройки подключения: `http://172.31.203.4:9090/ui/#/setup?hostname=172.31.203.4&port=9090`.

Провайдеры называются по ENV-источникам: **SUB1**, **SUB2**, **SRV1**, **SRV2** и далее. Их содержимое отображается раздельно; общие группы выбора и проверки задержки используют все провайдеры. Xray-подключения имеют префикс `[Xray]`; их тип в Mihomo — локальный SOCKS. Исходный протокол обслуживает Xray. Нативные Mihomo-подключения сохраняют свой тип.

Для выбора подключения: SELECTOR → MANUAL → нужный узел. HTTP/SOCKS-прокси доступен на **172.31.203.4:1080**. Установка контейнера сама по себе не направляет весь трафик LAN через VPN. Прозрачная маршрутизация на RouterOS настраивается отдельно для выбранных устройств.

## Как работает сеть

Сборка использует один режим на ARMv7, ARM64 и AMD64, без автоматического выбора по nftables.

По умолчанию `JACKETT_NETWORK_MODE=tun`. Mihomo создаёт `Meta`, но не устанавливает автоматические глобальные маршруты. Запускатель устанавливает отдельную таблицу 2022 и правила 12000–12020 **только для пакетов, пришедших через физический интерфейс контейнера**. Собственные соединения Xray, загрузка подписок, DNS и ответы GUI идут через исходный шлюз. Локальные адреса, связанные сети и частные сети исключены из VPN-перехвата. Таблица `main` и стандартный шлюз не заменяются.

RouterOS продолжает выбирать трафик, который направляется на IP контейнера через свою таблицу `vpn`. Сам IP/сеть контейнера не должен попадать под такие правила RouterOS. Требуется один физический интерфейс с default gateway. Отсутствие TUN или ошибка настройки останавливают контейнер, вместо установки небезопасного глобального маршрута.

Для работы только с явным прокси, без прозрачной маршрутизации:

```routeros
/container/envs/add list=jackett key=JACKETT_NETWORK_MODE value=proxy
```

Если ключ уже существует, измените значение вместо создания дубликата. Режим `proxy` оставляет GUI на порту 9090 и HTTP/SOCKS на порту 1080, не создаёт TUN и правил маршрутизации. Старые ENV `TUN`, `TUN_AUTO_ROUTE`, `TUN_AUTO_REDIRECT` больше не выбирают режим; их можно удалить. Значения `true` для авто-маршрутов принудительно заменяются безопасными `false`.

При первом обновлении проверяйте локально, сохранив возможность входа в MikroTik по MAC. Оставьте автозапуск выключенным до проверки GUI, подписок, SOCKS и перенаправления с обычного LAN-устройства. Проверки сборки на Linux не заменяют проверку реального RouterOS.

После проверки GUI, подписок и выбранного способа подключения включите автозапуск:

```routeros
/container/set [/container/find where name=jackett-mihomo-xray] start-on-boot=yes
```

## Справочник ENV

| Переменная | Назначение |
|---|---|
| SUB1, SUB2, SUB3, … | HTTP/HTTPS URL подписки |
| SRV1, SRV2, SRV3, … | Отдельная ссылка, Xray JSON или URL источника |
| PROVIDER_INTERVAL | Автоматическое обновление источников; по умолчанию 3600 секунд, минимум 60. Ручное обновление provider сразу перепроверяет исходную подписку. |
| SUB_USER_AGENT | По умолчанию Happ/1.0 Jackett-Bridge |
| HWID | Идентификатор для ограниченных подписок; автоматически сохраняется в каталоге конфигурации |
| LOG_LEVEL | Уровень журнала Mihomo; Xray пишет warning |
| EXTERNAL_UI_URL | URL ZIP веб-панели |
| UI_SECRET | Необязательный пароль API; без него или при пустом значении пароль не требуется |
| MIXED_PORT | Порт HTTP/SOCKS, по умолчанию 1080 |
| UI_PORT | Порт API/UI, по умолчанию 9090 |
| WORKDIR | Каталог конфигурации, по умолчанию /etc/mihomo |
| JACKETT_NETWORK_MODE | `tun` по умолчанию: прозрачный входящий трафик; `proxy`: только HTTP/SOCKS, без TUN |
| DNS_*, HEALTH_CHECK_* | Настройки DNS и проверок доступности |
| TUN_AUTO_ROUTE, TUN_AUTO_REDIRECT | Всегда `false` в нашей сборке, пользовательское `true` не включается |

Максимум 64 Xray-подключения; каждое работает отдельным процессом Xray. Потребление памяти зависит от количества подключений. Каталог /etc/mihomo находится внутри root-dir контейнера: в нём HWID, кеш и конфигурации с приватными данными. При удалении контейнера эти данные удаляются вместе с ним.

Выбранные режимы `AUTO`, `MANUAL`, `FALLBACK`, `LOADBALANCE` и узел внутри `MANUAL` сохраняются в `/etc/mihomo/cache.db` и восстанавливаются после обычного перезапуска контейнера. Сборка принудительно включает это сохранение, даже если в старом списке ENV осталось `STORE_SELECTED=false`. При удалении `root-dir`, создании контейнера с новым `root-dir` или очистке `cache.db` выбор начинается заново.

## Протоколы и форматы

| Вход | Обработка |
|---|---|
| VLESS URI | Xray; TCP/RAW, gRPC, XHTTP, WS, HTTPUpgrade, mKCP; TLS/REALITY в сочетаниях, принимаемых ядром |
| VMess URI | Xray; основные параметры транспорта |
| Trojan URI | Xray с сохранением параметров транспорта |
| Shadowsocks SIP002 URI | Xray; плагины требуют явной нативной конфигурации |
| `hysteria2://`, `hy2://` | Xray; базовый Hysteria2/TLS. Для advanced/obfs использовать полный Xray JSON |
| `wireguard://`, `wg://` | Xray; ключи, адрес, peer, MTU, reserved, keepalive |
| SOCKS/HTTP/HTTPS URI | Xray |
| Полный Xray JSON | Сохраняет outbounds, streamSettings, FinalMask, DNS, policy, маршрутизацию и зависимости; локальные inbounds заменяются на SOCKS 127.0.0.1. Внешние API/metrics/reverse удаляются |
| MASQUE, XDRIVE | Через полный Xray JSON; настройки транспорта не преобразуются в урезанный URI |
| Нативные TUIC/SSR/Hysteria v1/AnyTLS/SSH/Snell/Mieru URI | Mihomo, если его собственный URI-парсер принимает формат |
| Mihomo YAML/JSON `proxies` | Остается нативным Mihomo, без потери нестандартных настроек. Здесь доступны AmneziaWG и другие реализованные в исходном ядре типы |

Не все протоколы имеют стандартную share-ссылку. Произвольные возможности Xray 26.10.21 доступны через JSON и проверяются самим ядром. Неизвестные параметры URI отвергаются явно; используйте JSON вместо их молчаливого удаления. `support-x25519mlkem768` распознаётся как метаданные совместимости клиента; REALITY использует реализацию самого Xray. XHTTP `extra` и `x_padding_bytes` сохраняются.

Не смешивайте нативные URI и нативные YAML-объекты внутри одного источника; разные источники могут использовать разные форматы. Их можно смешивать с Xray-профилями. При автоматическом обновлении исходных URL адаптер обновляет локальные узлы с интервалом `PROVIDER_INTERVAL`. Кнопка ручного обновления provider в панели немедленно перепроверяет исходную подписку и возвращает Mihomo уже новый локальный список; перезапуск контейнера для появления нового узла не требуется.

MTProto — Telegram-прокси, а не VPN для произвольных приложений. Он здесь не эмулируется. Неподдерживаемые ядрами протоколы эта сборка не изобретает. Реальный gRPC/WS/mKCP зависит также от сервера: существующие серверные инбаунды не создаются автоматически.

## Образ с готовым GUI

Если контейнер не может скачать интерфейс с GitHub, используйте:

```text
ghcr.io/itnetsystem/jackett-mihomo-xray:with-ui
```

Zashboard 3.29.1 включён в образ; ZIP закреплён по версии и SHA256. При запуске интерфейс копируется в каталог UI, и скачивание с GitHub не требуется. Подписки всё равно требуют доступа к своим серверам. Архитектуры, ENV, сеть и протоколы совпадают с `latest`. Дополнительное место занимает сам интерфейс и его рабочая копия. Обновление версии GUI выполняется выпуском нового образа.

Для новой установки замените `:latest` на `:with-ui` в команде `container/add`. Для существующего контейнера:

```routeros
/container/set [/container/find where name=jackett-mihomo-xray] start-on-boot=no
/container/stop [/container/find where name=jackett-mihomo-xray]
```

Дождитесь `STOPPED`. Перед обновлением сохраните нужные конфигурации и HWID, затем:

```routeros
/container/set [/container/find where name=jackett-mihomo-xray] remote-image=ghcr.io/itnetsystem/jackett-mihomo-xray:with-ui
/container/repull [/container/find where name=jackett-mihomo-xray]
```

После окончания распаковки:

```routeros
/container/start [/container/find where name=jackett-mihomo-xray]
```

Существующий `EXTERNAL_UI_URL` можно оставить: встроенный `index.html` уже есть, поэтому стартовая загрузка не требуется. Автозапуск включите после проверки. GUI — [Zashboard](https://github.com/Zephyruso/zashboard).

## Обновление образа

```routeros
/container/set [/container/find where name=jackett-mihomo-xray] start-on-boot=no
/container/stop [/container/find where name=jackett-mihomo-xray]
/container/print
```

Дождитесь состояния `STOPPED`, затем загрузите обновление:

```routeros
/container/repull [/container/find where name=jackett-mihomo-xray]
```

После окончания загрузки и распаковки запустите:

```routeros
/container/start [/container/find where interface=veth1jackett]
```

Для перехода на другой тег перед repull измените remote-image через `/container/set`. ENV сохраните; перед repull сохраните нужные конфигурации и HWID: данные внутри root-dir могут быть заменены при переустановке. Не используйте один root-dir для нескольких контейнеров.

## Удаление контейнера

Отдельный скрипт не нужен. Остановите контейнер, дождитесь состояния stopped и удалите его через Remove в WinBox или командой:

```routeros
/container/stop [/container/find where interface=veth1jackett]
/container/print
```

После остановки:

```routeros
/container/remove [/container/find where interface=veth1jackett]
```

Дождитесь завершения удаления: RouterOS удаляет root-dir **containers/jackett** вместе с внутренними конфигурациями, кешем и HWID. Отдельный скрипт очистки не нужен. Общая /containers, Docker Bridge, veth1jackett и ENV jackett сохраняются.

При переустановке используйте существующие ENV и выполните container/add. HWID будет создан заново; для подписок с привязкой устройства можно заранее задать прежний HWID через ENV.

## Надёжность

Новые Xray-конфигурации проверяются перед заменой работающих. Сбой сети или некорректное обновление сохраняет последний рабочий набор. Недоступный источник без кэша отключается отдельно: остальные SUB/SRV продолжают работать. Ответ 401/403/404 отключает этот источник без использования старого кэша. Если доступных подключений не осталось, адаптер останавливается. Завершение Xray или Mihomo останавливает контейнер с ошибкой.

Кастомные шаблоны должны поддерживать PROVIDERS_BLOCK/PROVIDERS_LIST. Правила из полной YAML-подписки не импортируются: используются правила шаблона Mihomo. Служебные строки happ:// и incy://routing/ в подписке не считаются VPN-подключениями и пропускаются; клиентский routing из них автоматически в Mihomo не переносится.

## Документация RouterOS

- [Container](https://manual.mikrotik.com/docs/containers/)
- [VETH](https://manual.mikrotik.com/docs/containers/veth/)
- [Параметры container](https://manual.mikrotik.com/docs/cli-reference/container/)

## GHCR и Docker Hub одновременно

Поле registry-url задаёт один реестр по умолчанию. Современный RouterOS позволяет указать реестр непосредственно в remote-image, поэтому контейнеры из GHCR и Docker Hub могут работать и загружаться на одном роутере:

```text
ghcr.io/itnetsystem/jackett-mihomo-xray:latest
registry-1.docker.io/wiktorbgu/mihomo-mikrotik:latest
```

Если используется полное имя с реестром, переключать глобальный registry-url для каждой загрузки не требуется. Короткие имена без реестра используют registry-url. Можно оставить Docker Hub реестром по умолчанию, а Jackett всегда указывать с ghcr.io:

```routeros
/container/set [/container/find where interface=veth1jackett] remote-image=ghcr.io/itnetsystem/jackett-mihomo-xray:latest
/container/config/set registry-url=https://registry-1.docker.io
```

Это меняет параметры будущих загрузок, без остановки работающего контейнера. Поддержка реестра в remote-image указана в [журнале RouterOS](https://forum.mikrotik.com/t/v7-18-2-stable-is-released/182200).

## Размер образа

Сохранены Mihomo 1.19.33, Xray 26.10.21 и базы Xray GeoIP/GeoSite. Стандартная библиотека Python хранится в поддерживаемом Python ZIP-формате; удалён предкомпилированный кеш, запись нового pycache отключена. Размер файловой системы зависит от архитектуры и версии сборки; ориентируйтесь примерно на 160 МиБ до загрузки интерфейса и кеша. Интерфейс дополнительно скачивается при запуске. Реестр передаёт сжатые слои, а распаковка требует дополнительного свободного места.

Используйте постоянный накопитель. Для скачивания и распаковки нужно больше свободного места, чем занимает готовая файловая система. Веб-панель и кеш занимают дополнительное место.

