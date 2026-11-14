# 5.5.7 Packet Tracer — Explore Network Protocols: заметки к стенду

## Среда

`env: vm` (ВМ GitHub Actions, Ubuntu 24.04, systemd). Packet Tracer в CI недоступен, поэтому
топология активности воспроизведена сетевыми пространствами имён Linux: одно пространство на
устройство PT, имя пространства = имя устройства, адреса — из таблицы адресации методички.
Все службы настоящие (dnsmasq, chrony, nginx, net-snmp, aiosmtpd, pyftpdlib), трафик идёт
через veth-«кабели», мосты-коммутаторы и маршрутизаторы-пространства. Команда на устройстве:
`sudo ip netns exec <УСТРОЙСТВО> <команда>`.

## Топология

```
                 +------------------------- Internet --------------------------+
                 | to-R1 10.1.1.1/30   to-R3 10.2.2.1/30   to-Example 64.100.0.1/24
                 +--------+-------------------+--------------------+-----------+
                          |                   |                    |
                 Gi0-0-1 10.1.1.2     Gi0-0-0 10.2.2.2     eth0 64.100.0.10
                        [R1]                [R3] SNMP (read/write)  [Example-Server]
                 Gi0-0-0 209.165.200.225     Gi0-0-1 172.16.3.1      DNS, HTTP, EMAIL
                          |                   |  (Vlan1: dummy, down)
            vlan2 209.165.200.226 (+.227 NAT) [S3] мост
                     [FIREWALL] iptables     |
     vlan1 192.168.1.1  |   vlan3 192.168.2.1  eth0 172.16.3.2 [PC-B], DNS 64.100.0.10
             |          +-------------------- eth0 192.168.2.3 [DEVASC-Server] HTTP -> HTTPS
          [S2] мост, Vlan1 192.168.1.4 (эмулятор IOS: SSH, консоль, NTP-клиент)
           /        \
 eth0 192.168.1.3    eth0 192.168.1.2 -> DHCP (192.168.1.10)
 [Corporate]         [PC-A]
 DNS, DHCP, NTP, FTP
```

| Устройство PT | Пространство имён | Что работает |
|---|---|---|
| Corporate (сервер) | `Corporate` | dnsmasq (DNS), dnsmasq (DHCP), chronyd (NTP), pyftpdlib (FTP) |
| S2 (коммутатор) | `S2` | мост Linux + `src/s2_switch.py` (эмулятор IOS из `tools/csr1kv_emulator`) |
| PC-A | `PC-A` | клиенты: ping, busybox udhcpc, telnet, ssh, curl, ftp (tnftp) |
| FIREWALL (ASA) | `FIREWALL` | iptables: зоны, статический NAT, цепочка `OUTSIDE-DMZ` |
| DEVASC Server | `DEVASC-Server` | nginx (HTTP, затем HTTPS) |
| R1, R3 | `R1`, `R3` | маршрутизация; на R3 snmpd (community `read`/`write`) |
| «Internet» | `Internet` | маршрутизатор облака (10.1.1.1, 10.2.2.1, 64.100.0.1) |
| Example Server | `Example-Server` | dnsmasq (DNS), nginx (HTTP), `src/email_server.py` (SMTP+POP3) |
| S3, PC-B | `S3`, `PC-B` | мост; клиенты: ping, curl, snmpget/snmpwalk |

`prepare.sh` поднимает только то, что в .pka настроено заранее (топология, NAT и ACL на
FIREWALL, SSH на S2, SNMP на R3, DNS/HTTP Example Server, HTTP DEVASC Server, sampleFile.txt).
Всё, что настраивает студент, выполняется шагами сценария, файлы настроек показываются `cat`.

## Соответствие частям методички

| Часть | Действие в PT | На стенде |
|---|---|---|
| 1 | Corporate > DNS, запись www.example.com | `/etc/dnsmasq.d/Corporate-dns.conf`, dnsmasq; `dig` |
| 1 | DNS Server на PC-A / PC-B, ping, браузер | `/etc/netns/PC-A|PC-B/resolv.conf`; ping; `curl -i` |
| 2 | DHCP serverPool, IP Configuration > DHCP | `Corporate-dhcp.conf`; `busybox udhcpc` + `src/dhcp.sh`; leases |
| 3 | NTP On; S2: show clock detail, ntp server | chronyd; `sudo pt-console S2` (консоль); `chronyc clients` |
| 4 | telnet / ssh -l administrator с PC-A | telnet (закрывается), ssh, enable, exit |
| 5 | MIB Browser: .sysName, .ifOperStatus | `snmpwalk`/`snmpget -v2c -c read` по числовым OID |
| 6 | show run, `no access-list ... eq www`, HTTPS | `iptables -S`, `iptables -D OUTSIDE-DMZ ... --dport 80`; openssl + nginx 443 |
| 7 | EMAIL: SMTP/POP3, Student1/2; Compose/Receive/Reply | `email_server.py`; `curl smtp://` (отправка), `curl pop3://` (приём) |
| 8 | FTP: Student/class; ?, dir, put, get, delete, quit | `ftp_server.py` (pyftpdlib); интерактивный `ftp` |

Шаги `Part 0` — только показ стенда (список устройств и адресов), в методичке их нет.

## Отличия от методички

- Packet Tracer заменён пространствами имён; GUI-окна (Config, Services, Web Browser, Email,
  MIB Browser) заменены файлами настроек и консольными клиентами.
- Статический адрес PC-A до DHCP (192.168.1.2) взят из 5.4.6; шлюз DEVASC Server — 192.168.2.1
  (в таблице опечатка 192.168.1.1). IPv6 в пространствах отключён (в методичке только IPv4).
- S2 — эмулятор IOS, не Catalyst: часы до синхронизации идут от «аппаратного календаря»
  (00:00 UTC 1 марта 1993, как у коммутатора без батареи); после `ntp server` эмулятор делает
  настоящий NTP-запрос к chronyd и ставит время по первому корректному ответу (как SNTP, реальный
  IOS синхронизируется минуты). Порт 23 принимает соединение и сразу закрывает его
  (`transport input ssh`). Консоль — Unix-сокет и клиент `pt-console` вместо вкладки CLI.
- SNMP: community-строки работают только в v1/v2c, поэтому `-v2c` вместо «v3» PT. MIB-файлы
  IETF в Ubuntu не поставляются — OID числовые (`1.3.6.1.2.1.1.5.0` = sysName). У R3 добавлен
  выключенный интерфейс `Vlan1` (как в PT 2 из 3 интерфейсов up); `lo` исключается директивой
  `include_ifmib_iface_prefix`, если net-snmp её поддерживает.
- FIREWALL — iptables, а не ASA: «show run» = `iptables -S`, удаление строки ACL = `iptables -D`.
- HTTPS: сертификат самоподписанный (создаётся в сценарии), проверка `curl -vk`.
- EMAIL: SMTP — aiosmtpd, POP3 — минимальная реализация RFC 1939 (`src/email_server.py`);
  настройки клиентов PT передаются параметрами curl, письма составляются файлами `.eml`.
- FTP: файлы `asa842-k8.bin` и др. на сервере — заглушки (нули) тех же размеров, не образы Cisco.

## Что проверить в результатах прогона

1. `prepare.sh`: строки `WARNING` в логе шага (S2, ping через NAT, HTTP, DNS, SNMP).
2. AppArmor (dnsmasq, chronyd): службы запускаются с путями из профилей; при отказе — сообщение
   `Permission denied` в шагах `corp_dns_on`, `corp_dhcp_on`, `corp_ntp_on`.
3. `pca_dhcp`: аренда 192.168.1.10 (dhcp-sequential-ip); `s2_console_ntp`: вторая
   `show clock detail` показывает `Time source is NTP`.
4. `pcb_snmp_ifoper`: число интерфейсов (3 при поддержке `include_ifmib_iface_prefix`, иначе 4).
5. `pca_ftp`: подсказки tnftp (`Name (...)`, `ftp> `) совпали с ожиданиями interact.

## Исправление после первого прогона

В первом прогоне кабели (veth) создавались в корневом пространстве имён под временными именами
`lab-a`/`lab-b`. systemd на Ubuntu 24.04 (MACAddressPolicy=persistent) выдавал им MAC-адреса по имени,
поэтому у всех кабелей оказались одинаковые MAC и мосты S2/S3 не пересылали кадры. Теперь пара veth
создаётся сразу внутри пространств имён, как в работе 5.4.
