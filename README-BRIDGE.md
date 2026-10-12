# Mihomo + Xray: подписки через ENV для MikroTik

Образ: `ghcr.io/itnetsystem/jackett-mihomo-xray:mikrotik-all-xray26.10.10-v1`.
Архитектуры: ARM64 (RB5009), AMD64. Mihomo 1.19.32 + Xray 26.10.10. Это новая отдельная сборка; прежние экспериментальные теги сохраняются.

Для каждого Xray-подключения запускается отдельный экземпляр Xray с локальным SOCKS, сохраняющий параметры соответствующего профиля. Mihomo предоставляет TProxy/TUN, DNS, правила, группы выбора и веб-панель. Максимум 64 Xray-подключения; потребление памяти больше, чем у обычного Mihomo, поэтому начинайте с отдельного контейнера.

## Основные ENV

| Переменная | Назначение |
|---|---|
| `SUB1`, `SUB2`, … | HTTP/HTTPS URL подписки: raw/base64 URI, полный Xray JSON или Mihomo YAML |
| `SRV1`, `SRV2`, `SRV2_TEST`, … | Отдельная ссылка, Xray JSON или URL подписки |
| `PROVIDER_INTERVAL` | Обновление источников в секундах; по умолчанию 3600, минимум 60 |
| `SUB_USER_AGENT` | По умолчанию `Happ/1.0 Jackett-Bridge`, чтобы получать исходные ссылки вместо Clash YAML |
| `HWID` | HWID для ограниченных подписок; если не задан, сохраняется в `/etc/mihomo/.hwid` |
| `LOG_LEVEL` | Лог Mihomo: warning, info, debug и т. д. Xray пишет warning без дампа конфигурации |
| `EXTERNAL_UI_URL` | URL ZIP веб-панели, как у wiktorbgu/mihomo-mikrotik |
| `UI_SECRET` | Пароль API Mihomo |
| `MIXED_PORT` | SOCKS/HTTP-порт; по умолчанию 1080 |
| `UI_PORT` | API и веб-панель; по умолчанию 9090 |
| `WORKDIR` | Каталог конфигурации; по умолчанию `/etc/mihomo` |
| `CONFIG`, `TUN`, `IPTABLES`, `DNS_*`, `HEALTH_CHECK_*` | Исходная обработка шаблонов и сети wiktorbgu сохранена |

Отключенные ENV RouterOS не передаются контейнеру. Для обычной подписки достаточно SUB/SRV, без загрузки файлов. `JACKETT_XRAY_TEST` для этой сборки не требуется.

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

## Настройка на вашем MikroTik

Рабочий контейнер и его папку `/containers/mihomo` не менять. В командах используется ваш интерфейс **`veth-jackett`**. Проверьте его адрес и шлюз перед запуском. Для сети 172.31.203.0/24 ваш шлюз — **172.31.203.254**, DNS 1.1.1.1.

Скопировать SUB1 без вывода приватной ссылки:

```routeros
/container/envs/add list=mihomo-test key=SUB1 value=[/container/envs/get [/container/envs/find where list=mihomo and key=SUB1] value]
```

Если SUB1 в тестовом списке уже есть, вместо add используйте set:

```routeros
/container/envs/set [/container/envs/find where list=mihomo-test and key=SUB1] value=[/container/envs/get [/container/envs/find where list=mihomo and key=SUB1] value]
```

Настройки UI/LOG_LEVEL копируются таким же способом. Не копируйте отключенные SRV, если они не нужны. Для подписки с лимитом устройств необходимо сохранить HWID рабочего клиента; домашняя подписка сейчас без HWID-лимита.

Обновить существующий контейнер на `veth-jackett` (его ENV и mounts сохраняются):

```routeros
/container/stop [/container/find where interface=veth-jackett]
/container/set [/container/find where interface=veth-jackett] remote-image=itnetsystem/jackett-mihomo-xray:mikrotik-all-xray26.10.10-v1 dns=1.1.1.1
/container/repull [/container/find where interface=veth-jackett]
```

Дождаться завершения downloading/extracting в `/container/print`, затем:

```routeros
/container/start [/container/find where interface=veth-jackett]
```

В RouterOS с `list` для mounts используйте `mountlists`, а не старый `mounts`. Нужен отдельный writable mount `/containers/mihomo-test` → `/etc/mihomo`, Перед новой установкой создайте этот mountlist; при обновлении существующие mounts сохраняются. Конфигурации/кеш с секретами находятся в `.jackett-xray` внутри него: не публикуйте эту папку.

Веб-панель: `http://IP-КОНТЕЙНЕРА:9090/ui/`. В настройках подключения укажите IP интерфейса `veth-jackett`, порт 9090 и ваш API secret. Если задан UI_SECRET, введите его в настройках подключения. После загрузки будет провайдер `JACKETT_XRAY`, а названия подключений Xray начинаются с `[Xray]`. Нативные подключения сохраняют свой тип, например TUIC.

Для явного выбора: SELECTOR → MANUAL → нужная локация. Проверка браузером/компьютером через HTTP proxy `IP-КОНТЕЙНЕРА:1080`. Веб-панель скачивается при запуске по EXTERNAL_UI_URL; для этого нужны работающие шлюз/DNS/интернет. Доступность страницы API не означает, что UI уже скачан.

## Новая установка

При уже подготовленных отдельном veth, ENV и writable mountlist:

```routeros
/container/config/set registry-url=https://ghcr.io; /container/add remote-image=itnetsystem/jackett-mihomo-xray:mikrotik-all-xray26.10.10-v1 envlists=mihomo-test interface=veth-jackett root-dir=/containers/jackett-root mountlists=aportnov-test-config dns=1.1.1.1 logging=yes start-on-boot=no
```

Пример одной ссылки:

```routeros
/container/envs/add list=mihomo-test key=SRV1 value="vless://YOUR-UUID@YOUR-SERVER:443?type=grpc&security=tls&sni=YOUR-SNI&serviceName=YOUR-SERVICE#My-GRPC"
```

Нельзя повторно использовать одинаковый root-dir для двух контейнеров. Не запускайте одновременно два контейнера на одном veth. Общий registry-url влияет на будущие загрузки других образов; существующие работающие контейнеры не меняются.

## Надежность и откат

Все новые Xray-конфигурации проверяются до замены работающих. Сбой сети/некорректный ответ при обновлении сохраняет последний работающий набор; доступ к кешу только внутри локального каталога. Ответ 401/403/404 или пустая подписка останавливает мост вместо незаметного перехода на DIRECT. Завершение одного Xray или Mihomo завершает контейнер с ошибкой.

При использовании собственного шаблона он должен содержать PROVIDERS_BLOCK/PROVIDERS_LIST и направлять трафик в соответствующие группы. Кастомные ручные конфиги без этих вставок автоматически не дописываются. Правила маршрутизации из полной YAML-подписки не импортируются: используются правила исходного шаблона MikroTik/Mihomo.

Перед обновлением сохраните прежний тег образа и настройки контейнера. При откате восстановите прежний тег и ENV. В сохранённом каталоге конфигурации удалите только `user_sh/jackett-all-xray.sh` перед запуском старого образа: этот hook относится к новому адаптеру.

## Проверено

- Девять тестов преобразования: flow/REALITY, gRPC/XHTTP extra, base64, JSON, native YAML, Hysteria2, SS и отказ от неизвестных параметров.
- Домашняя подписка: 8/8 конфигураций приняты Xray 26.10.10 и видны в API Mihomo как локальные SOCKS.
- С VPN1 все 8/8 TCP/XHTTP до внешнего HTTPS вернули 204, включая Гонконг через Сербию и Эстонию.
- Смешанный провайдер: восемь Xray-подключений и нативный TUIC, без потери типа.
- Новую сборку ещё нужно проверить на вашем RB5009; предыдущая версия с двумя тестовыми протоколами там уже работала.

- Автообновление SUB1 проверено: добавленное подключение появилось в провайдере без перезапуска контейнера.
