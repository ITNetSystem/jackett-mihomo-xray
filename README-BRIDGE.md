# Jackett Mihomo + Xray — чистая установка на MikroTik

Образ: `ghcr.io/itnetsystem/jackett-mihomo-xray:mikrotik-all-xray26.10.10-v1`.
Mihomo 1.19.32 + Xray 26.10.10. Архитектуры ARM64 и AMD64.

Подключения добавляются через ENV. SUB1/SUB2 содержат адреса подписок, SRV1/SRV2 — отдельные ссылки. Источники объединяются в провайдер JACKETT_XRAY и обновляются автоматически. Файлы конфигурации для обычной подписки создаются контейнером.

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

Подтвердите изменение физически способом, указанным RouterOS. Подготовьте доступное хранилище: ниже пример для диска **disk1**. Если он называется иначе, замените `disk1` во всех путях. Каталоги должны быть новыми; не используйте папки другого контейнера.

```routeros
/file/add name=disk1/jackett type=directory
/file/add name=disk1/jackett/config type=directory
/file/add name=disk1/jackett/tmp type=directory
/container/config/set registry-url=https://ghcr.io tmpdir=disk1/jackett/tmp
/container/mounts/add list=jackett src=/disk1/jackett/config dst=/etc/mihomo mode=rw
```

## 2. Сеть контейнера

Пример использует отдельную сеть **192.168.240.0/24**. Убедитесь, что она свободна; при необходимости замените её во всех командах. Адрес роутера/шлюза 192.168.240.1, контейнера 192.168.240.2.

```routeros
/interface/bridge/add name=bridge-jackett
/ip/address/add address=192.168.240.1/24 interface=bridge-jackett
/interface/veth/add name=veth-jackett address=192.168.240.2/24 gateway=192.168.240.1
/interface/bridge/port/add bridge=bridge-jackett interface=veth-jackett
/ip/firewall/nat/add chain=srcnat src-address=192.168.240.0/24 out-interface-list=WAN action=masquerade comment="Jackett container Internet"
```

В примере WAN — существующий список внешних интерфейсов. Если его нет, в правиле NAT замените `out-interface-list=WAN` на `out-interface=ИМЯ_ВАШЕГО_WAN`. Контейнер должен выходить в интернет обычным маршрутом; не направляйте его собственный трафик обратно через него.

При блокирующих правилах forward разрешите трафик контейнера в WAN, ответный established/related и доступ из доверенной LAN к TCP 1080/9090. Разрешения должны стоять перед блокирующими правилами. Например, если у вас настроены списки LAN и WAN:

```routeros
/ip/firewall/filter/add chain=forward action=accept dst-address=192.168.240.2 connection-state=established,related place-before=0 comment="Jackett return traffic"
/ip/firewall/filter/add chain=forward action=accept src-address=192.168.240.2 out-interface-list=WAN place-before=0 comment="Jackett outbound"
/ip/firewall/filter/add chain=forward action=accept in-interface-list=LAN dst-address=192.168.240.2 protocol=tcp dst-port=1080,9090 place-before=0 comment="Jackett LAN access"
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

Готовую ссылку `wireguard://…` или `wg://…` вставьте целиком в `SRV1` или `SRV2`. Символы `+`, `/` и `=` внутри PrivateKey, PublicKey и PresharedKey заменять вручную не нужно. Уже закодированные ссылки с `%2B`, `%2F`, `%3D` также принимаются без изменений.

```routeros
/container/envs/add list=jackett key=SRV1 value="wireguard://PRIVATE_KEY@SERVER:51820?address=10.7.0.2/32&publickey=SERVER_PUBLIC_KEY&allowedips=0.0.0.0/0&keepalive=25#WireGuard"
```

Это пример структуры: замените PRIVATE_KEY, SERVER и SERVER_PUBLIC_KEY значениями своего подключения. Готовую ссылку изменять не требуется. Файл `.conf` с разделами Interface/Peer не является ссылкой и напрямую в SRV не принимается.

## 4. Загрузка и запуск

После подготовки сети, mounts и ENV установка выполняется одной командой:

```routeros
/container/add remote-image=itnetsystem/jackett-mihomo-xray:mikrotik-all-xray26.10.10-v1 envlists=jackett interface=veth-jackett root-dir=disk1/jackett/root mountlists=jackett dns=1.1.1.1 logging=yes start-on-boot=yes
```

Дождитесь завершения downloading/extracting:

```routeros
/container/print detail
/container/start [/container/find where interface=veth-jackett]
```

В современных RouterOS используются `envlists` и `mountlists`. Старые версии могут иметь другой синтаксис; инструкция рассчитана на версию с этими параметрами.

## 5. Веб-панель и подключение

Откройте `http://192.168.240.2:9090/ui/`. Укажите hostname **192.168.240.2**, port **9090**, secret — значение UI_SECRET; если пароль не задавали, оставьте поле secret пустым. Если нужна страница настройки подключения: `http://192.168.240.2:9090/ui/#/setup?hostname=192.168.240.2&port=9090`.

Провайдер называется **JACKETT_XRAY**. Xray-подключения имеют префикс `[Xray]`; их тип в Mihomo — локальный SOCKS. Исходный протокол обслуживает Xray. Нативные Mihomo-подключения сохраняют свой тип.

Для выбора подключения: SELECTOR → MANUAL → нужный узел. HTTP/SOCKS-прокси доступен на **192.168.240.2:1080**. Установка контейнера сама по себе не направляет весь трафик LAN через VPN. Прозрачная маршрутизация на RouterOS настраивается отдельно для выбранных устройств.

## ENV

| Переменная | Назначение |
|---|---|
| SUB1, SUB2, SUB3, … | HTTP/HTTPS URL подписки |
| SRV1, SRV2, SRV3, … | Отдельная ссылка, Xray JSON или URL источника |
| PROVIDER_INTERVAL | Обновление источников; по умолчанию 3600 секунд, минимум 60 |
| SUB_USER_AGENT | По умолчанию Happ/1.0 Jackett-Bridge |
| HWID | Идентификатор для ограниченных подписок; автоматически сохраняется в каталоге конфигурации |
| LOG_LEVEL | Уровень журнала Mihomo; Xray пишет warning |
| EXTERNAL_UI_URL | URL ZIP веб-панели |
| UI_SECRET | Необязательный пароль API; без него или при пустом значении пароль не требуется |
| MIXED_PORT | Порт HTTP/SOCKS, по умолчанию 1080 |
| UI_PORT | Порт API/UI, по умолчанию 9090 |
| WORKDIR | Каталог конфигурации, по умолчанию /etc/mihomo |
| CONFIG, TUN, IPTABLES, DNS_*, HEALTH_CHECK_* | Настройки исходных шаблонов wiktorbgu |

Максимум 64 Xray-подключения; каждое работает отдельным процессом Xray. Потребление памяти зависит от количества подключений. Сохраняйте writable каталог /etc/mihomo: в нём HWID, кеш и конфигурации с приватными данными.

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

Не все протоколы имеют стандартную share-ссылку. Произвольные возможности Xray 26.10.10 доступны через JSON и проверяются самим ядром. Неизвестные параметры URI отвергаются явно; используйте JSON вместо их молчаливого удаления. `support-x25519mlkem768` распознаётся как метаданные совместимости клиента; REALITY использует реализацию самого Xray. XHTTP `extra` и `x_padding_bytes` сохраняются.

Не смешивайте нативные URI и нативные YAML-объекты в одной конфигурации источников; выберите один формат для нативных Mihomo-узлов. Их можно смешивать с Xray-профилями. При обновлении исходных URL адаптер обновляет локальные узлы, а Mihomo опрашивает локальный провайдер каждые 60 секунд. Новые узлы могут появиться в UI спустя ещё минуту после обновления источника.

MTProto — Telegram-прокси, а не VPN для произвольных приложений. Он здесь не эмулируется. Неподдерживаемые ядрами протоколы эта сборка не изобретает. Реальный gRPC/WS/mKCP зависит также от сервера: существующие серверные инбаунды не создаются автоматически.

## Обновление образа

```routeros
/container/stop [/container/find where interface=veth-jackett]
/container/repull [/container/find where interface=veth-jackett]
```

Дождитесь загрузки/распаковки, затем:

```routeros
/container/start [/container/find where interface=veth-jackett]
```

Для перехода на другой тег перед repull измените remote-image через `/container/set`. ENV и writable каталог сохраняйте. Не используйте один root-dir для нескольких контейнеров.

## Надёжность

Новые Xray-конфигурации проверяются перед заменой работающих. Сбой сети или некорректное обновление сохраняет последний рабочий набор. Ответ 401/403/404 или пустая подписка останавливает адаптер. Завершение Xray или Mihomo останавливает контейнер с ошибкой.

Кастомные шаблоны должны поддерживать PROVIDERS_BLOCK/PROVIDERS_LIST. Правила из полной YAML-подписки не импортируются: используются правила шаблона Mihomo.

## Документация RouterOS

- [Container](https://manual.mikrotik.com/docs/containers/)
- [VETH](https://manual.mikrotik.com/docs/containers/veth/)
- [Параметры container](https://manual.mikrotik.com/docs/cli-reference/container/)
