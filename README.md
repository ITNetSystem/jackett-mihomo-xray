# VPN Jackett Xray для MikroTik

Xray-only контейнер с собственным контроллером и веб-интерфейсом VPN Jackett.

Образ: `ghcr.io/itnetsystem/jackett-mihomo-xray:latest`

Версионный тег: `ghcr.io/itnetsystem/jackett-mihomo-xray:xray-26.10.31`

Название пакета в GHCR сохранено прежним, чтобы существующие MikroTik могли сделать обычный `repull`. Внутри актуального образа Mihomo отсутствует.

## Что умеет

- Xray 26.10.31 и нативный Xray TUN;
- ARMv7, ARM64 и AMD64;
- источники `SUB1`, `SUB2`, `SRV1` и `XRAY_JSON1`;
- режимы «Вручную», «Авто» и «Резерв»;
- обновление подписки без перезапуска контейнера;
- сохранение режима и выбранного узла в `root-dir`;
- собственная панель VPN Jackett на порту 9090;
- SOCKS5 на порту 1080 и HTTP proxy на 1081.

Версия Xray отображается в разделе «Сведения о системе» панели, а не поверх стороннего GUI.

## Быстрый запуск

Создайте ENV-список `jackett` и добавьте хотя бы один источник:

```routeros
/container/envs/add list=jackett key=SUB1 value="https://vpn.jackett.ru/sub/ВАША_ССЫЛКА"
/container/envs/add list=jackett key=JACKETT_NETWORK_MODE value=tun
```

Добавьте контейнер, используя уже настроенный veth-интерфейс:

```routeros
/container/add name=jackett-mihomo-xray remote-image=ghcr.io/itnetsystem/jackett-mihomo-xray:latest envlists=jackett interface=veth1jackett root-dir=containers/jackett logging=yes start-on-boot=yes
```

Полная инструкция и безопасное обновление: [README-BRIDGE.md](README-BRIDGE.md).

## Поддерживаемые данные

Ссылки VLESS, VMess, Trojan, Shadowsocks, Hysteria2, WireGuard, SOCKS/HTTP и полные Xray JSON-конфигурации преобразуются без передачи секретной ссылки локальному GUI. Служебные `happ://` и `incy://routing/` пропускаются.

Mihomo YAML и специфичные только для Mihomo схемы намеренно отклоняются с понятной ошибкой: контейнер больше не содержит второе ядро и не делает вид, что такой узел работает.

## Сеть и отказобезопасность

В режиме `tun` Xray создает `xray0`. Контроллер ставит отдельную таблицу маршрутизации 2022 только для трафика, пришедшего от MikroTik через интерфейс контейнера. Собственные подключения Xray, загрузка подписки и панель продолжают использовать обычный шлюз, поэтому петли маршрутизации нет.

Новые профили сначала проверяются командой `xray run -test`. Некорректное обновление не заменяет работающий набор. Кэш, HWID, режим и выбранный узел находятся в прежнем каталоге `/etc/mihomo` внутри `root-dir` исключительно для совместимости обновления.

## Предыдущая версия

Последняя комбинированная сборка сохранена под тегом:

`ghcr.io/itnetsystem/jackett-mihomo-xray:mihomo-1.19.33-xray-26.10.31`

Тег `with-ui` больше не выпускается и удаляется из GHCR после публикации Xray-only версии.
