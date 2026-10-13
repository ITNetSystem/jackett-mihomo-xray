# Jackett Mihomo + Xray для MikroTik

**Mihomo 1.19.32 + Xray 26.10.10**, ARM64 и AMD64.

Образ: `ghcr.io/itnetsystem/jackett-mihomo-xray:mikrotik-all-xray26.10.10-v1`.

Подписки и отдельные подключения задаются через ENV: **SUB1, SUB2, SRV1, SRV2** и далее. Конфигурации создаются автоматически. Подключения объединяются в провайдер JACKETT_XRAY.

## Чистая установка

**[Пошаговая инструкция с нуля](README-BRIDGE.md)**: подготовка RouterOS, хранилища, сети, ENV, установка и открытие веб-панели.

В инструкции единые имена:

| Имя | Назначение |
|---|---|
| jackett-mihomo-xray | Имя контейнера |
| veth4jackett | Интерфейс контейнера |
| Docker Bridge | Мост сети контейнера |
| jackett | Список ENV |
| /containers/jackett | Каталог контейнера в корневой папке /containers |

После подготовки по инструкции контейнер добавляется одной командой:

```routeros
/container/add name=jackett-mihomo-xray remote-image=itnetsystem/jackett-mihomo-xray:mikrotik-all-xray26.10.10-v1 envlists=jackett interface=veth4jackett root-dir=containers/jackett dns=1.1.1.1 logging=yes start-on-boot=yes
```

Папка создаётся RouterOS при распаковке образа. Создание config/tmp и mountlist не требуется.

В ENV-команде `list=jackett` означает набор переменных, `key=SUB1` — имя переменной, `value` — её значение. ENV можно также добавлять в графическом интерфейсе RouterOS.

## Протоколы

Xray обслуживает VLESS, VMess, Trojan, Shadowsocks, SOCKS/HTTP и другие реализованные им протоколы. Для VLESS URI поддерживаются TCP/RAW, **gRPC**, XHTTP, WebSocket, HTTPUpgrade и mKCP. MASQUE, XDRIVE и расширенные настройки передаются полным Xray JSON. Нативные Mihomo-конфигурации остаются в Mihomo.

Поддержка протокола ядром и поддержка формата ссылки различаются; [таблица форматов и ограничений](README-BRIDGE.md#протоколы-и-форматы). Неизвестные параметры URI отклоняются явно. Серверные инбаунды автоматически не создаются.

## Порты

- **1080** — HTTP/SOCKS-прокси.
- **9090** — API и веб-панель; необязательный пароль задаётся UI_SECRET. Без него поле secret в веб-панели оставьте пустым.

Для обычной подписки дополнительные файлы конфигурации загружать не требуется. Настройка прозрачной маршрутизации LAN выполняется отдельно на RouterOS.

## Удаление

Остановите контейнер и удалите через Remove в WinBox — отдельный скрипт не нужен. Root-dir удаляется при штатном удалении. Все данные находятся внутри одного root-dir containers/jackett и удаляются вместе с контейнером; [подробнее об удалении](README-BRIDGE.md#удаление-контейнера).
