# Установка и обновление VPN Jackett Xray на MikroTik

## Перед началом

Контейнеру нужны:

- RouterOS с включенными containers;
- настроенный veth-интерфейс с выходом в интернет;
- постоянный `root-dir`;
- доступ к GHCR и адресу подписки;
- порт 9090, если панель должна открываться из вашей локальной сети.

Образ работает на ARMv7, ARM64 и AMD64. Внутри только Xray 26.10.31; отдельного образа с интерфейсом нет, потому что фирменная панель уже включена в `latest`.

## Новая установка

Ниже IP-адреса приведены как пример. Если veth и NAT уже работают, не создавайте их повторно.

```routeros
/interface/veth/add name=veth1jackett address=172.20.0.2/24 gateway=172.20.0.1
/ip/address/add address=172.20.0.1/24 interface=veth1jackett
/ip/firewall/nat/add chain=srcnat src-address=172.20.0.0/24 action=masquerade comment="VPN Jackett container"
```

Создайте ENV-список. `SUB1` можно повторить как `SUB2`, `SRV1` и далее:

```routeros
/container/envs/add list=jackett key=SUB1 value="https://vpn.jackett.ru/sub/ВАША_ССЫЛКА"
/container/envs/add list=jackett key=JACKETT_NETWORK_MODE value=tun
/container/envs/add list=jackett key=PROVIDER_INTERVAL value=3600
```

Создайте и запустите контейнер:

```routeros
/container/add name=jackett-mihomo-xray remote-image=ghcr.io/itnetsystem/jackett-mihomo-xray:latest envlists=jackett interface=veth1jackett root-dir=containers/jackett logging=yes start-on-boot=yes
/container/start [/container/find where name=jackett-mihomo-xray]
```

Откройте `http://172.20.0.2:9090/ui/`. В панели доступны:

- **Вручную** — всегда использовать выбранный узел;
- **Авто** — Xray выбирает живой узел с минимальной задержкой;
- **Резерв** — Xray использует доступный узел и возвращается к выбранному при отсутствии результатов проверки;
- **Обновить подписку** — перечитать исходные SUB/SRV без перезапуска контейнера.

## Обновление существующего контейнера

Старый `root-dir` сохраняйте: путь `/etc/mihomo` оставлен внутри образа специально для совместимости данных. ENV с параметрами стороннего интерфейса больше не нужен и игнорируется.

```routeros
/container/set [/container/find where name=jackett-mihomo-xray] start-on-boot=no
/container/stop [/container/find where name=jackett-mihomo-xray]
/container/set [/container/find where name=jackett-mihomo-xray] remote-image=ghcr.io/itnetsystem/jackett-mihomo-xray:latest
/container/repull [/container/find where name=jackett-mihomo-xray]
/container/start [/container/find where name=jackett-mihomo-xray]
```

После проверки:

```routeros
/container/set [/container/find where name=jackett-mihomo-xray] start-on-boot=yes
```

Если нужен откат, предыдущая комбинированная сборка сохранена как:

```routeros
/container/set [/container/find where name=jackett-mihomo-xray] remote-image=ghcr.io/itnetsystem/jackett-mihomo-xray:mihomo-1.19.33-xray-26.10.31
```

## Порты

| Порт | Назначение |
|---:|---|
| 9090/TCP | Панель и локальный API VPN Jackett |
| 1080/TCP/UDP | SOCKS5 |
| 1081/TCP | HTTP proxy |

Для обычного TUN-режима пробрасывать эти порты наружу Docker/MikroTik не требуется: они доступны по IP veth. Не публикуйте панель в интернет.

## Диагностика

```routeros
/container/print detail where name=jackett-mihomo-xray
/log/print where message~"jackett|Xray|container"
```

Нормальный запуск содержит строки `Bridge ready`, `Xray ... started` и `Network mode tun`. Если источник временно недоступен, используется последний проверенный кэш. Ответы 401/403/404 отключают именно этот источник; при отсутствии рабочих Xray-узлов контейнер завершится с ошибкой вместо прямого выхода в интернет.
