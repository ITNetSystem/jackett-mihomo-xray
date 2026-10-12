# Jackett Mihomo + Xray для MikroTik

**Mihomo 1.19.32 + Xray 26.10.10**, ARM64 и AMD64.

Образ: `ghcr.io/itnetsystem/jackett-mihomo-xray:mikrotik-all-xray26.10.10-v1`.

Подписки и отдельные подключения задаются через ENV: **SUB1, SUB2, SRV1, SRV2** и далее. Конфигурации создаются автоматически. Подключения объединяются в провайдер JACKETT_XRAY.

## Чистая установка

**[Пошаговая инструкция с нуля](README-BRIDGE.md)**: подготовка RouterOS, хранилища, сети, ENV, установка и открытие веб-панели.

В инструкции единые имена:

| Имя | Назначение |
|---|---|
| veth-jackett | Интерфейс контейнера |
| bridge-jackett | Мост сети контейнера |
| jackett | Список ENV и список mounts |
| disk1/jackett | Каталог на диске; замените disk1 на имя своего хранилища |

После подготовки по инструкции контейнер добавляется одной командой:

```routeros
/container/add remote-image=itnetsystem/jackett-mihomo-xray:mikrotik-all-xray26.10.10-v1 envlists=jackett interface=veth-jackett root-dir=disk1/jackett/root mountlists=jackett dns=1.1.1.1 logging=yes start-on-boot=yes
```

В ENV-команде `list=jackett` означает набор переменных, `key=SUB1` — имя переменной, `value` — её значение. ENV можно также добавлять в графическом интерфейсе RouterOS.

## Протоколы

Xray обслуживает VLESS, VMess, Trojan, Shadowsocks, SOCKS/HTTP и другие реализованные им протоколы. Для VLESS URI поддерживаются TCP/RAW, **gRPC**, XHTTP, WebSocket, HTTPUpgrade и mKCP. MASQUE, XDRIVE и расширенные настройки передаются полным Xray JSON. Нативные Mihomo-конфигурации остаются в Mihomo.

Поддержка протокола ядром и поддержка формата ссылки различаются; [таблица форматов и ограничений](README-BRIDGE.md#протоколы-и-форматы). Неизвестные параметры URI отклоняются явно. Серверные инбаунды автоматически не создаются.

## Порты

- **1080** — HTTP/SOCKS-прокси.
- **9090** — API и веб-панель; пароль задаётся UI_SECRET.

Для обычной подписки дополнительные файлы конфигурации загружать не требуется. Настройка прозрачной маршрутизации LAN выполняется отдельно на RouterOS.
