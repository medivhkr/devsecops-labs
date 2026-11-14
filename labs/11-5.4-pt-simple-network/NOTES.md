# 5.4.6 Packet Tracer - Explore a Simple Network: заметки к прогону

## Среда: vm

Cisco Packet Tracer на стенде недоступен (GUI, учётная запись NetAcad, файл .pka). Топология
воспроизведена на ВМ GitHub Actions Ubuntu 24.04 (`env: vm`) настоящими средствами Linux:
сетевые пространства имён (`ip netns`), пары veth, мосты Linux, iptables, `python3 -m http.server`.
Нужны root, systemd (`systemd-run` для HTTP-службы) и свой стек netfilter в каждом пространстве
имён, поэтому выбрана ВМ, а не контейнер. Для запуска нужен workflow с `env: vm`
(файл `.github/workflows/lab-5.4.yml`).

- `prepare.sh` строит исходную топологию **без PC-A и PC-B**, загружает базовые правила FIREWALL
  (`src/FIREWALL.rules`: static NAT, PAT, модель уровней безопасности ASA) и запускает HTTP-службу
  DEVASC Server.
- Сценарий: список доступа OUTSIDE-DMZ (видимые команды iptables, как исходная конфигурация .pka),
  затем Part 1-4 по порядку. Команда «на устройстве» = `sudo ip netns exec <УСТРОЙСТВО> <команда>`.

## Топология

```
 PC-A   Fa0 192.168.1.2/24, gw 192.168.1.1          (добавляется в сценарии, Part 1)
   |
 S2     br0: Fa0-2 (PC-A), Fa0-1 (FIREWALL)          inside 192.168.1.0/24
   |
 FIREWALL  VLAN1 192.168.1.1/24  (inside, 100)
           VLAN3 192.168.2.1/24  (dmz, 70) -------- Fa0 DEVASC-Server  192.168.2.3/24
           VLAN2 209.165.200.226/29 (outside, 0)        gw 192.168.1.1 (onlink), www.devasc-netacad.pka
                 209.165.200.227/32 = static NAT -> 192.168.2.3
   |
 R1     G0-0-0 209.165.200.225/29
        G0-0-1 10.1.1.2/30
   |
 Internet  to-R1 10.1.1.1/30                          облако, один маршрутизатор (восстановлено по смыслу)
           to-Example 64.100.0.1/24 --------------- Fa0 Example-Server 64.100.0.10/24
           to-R3 10.2.2.1/30                             gw 64.100.0.1, www.example.com
   |
 R3     G0-0-0 10.2.2.2/30
        G0-0-1 172.16.3.1/24
   |
 S3     br0: G0-1 (R3), Fa0-2 (PC-B)                 LAN 172.16.3.0/24
   |
 PC-B   Fa0 172.16.3.2/24, gw 172.16.3.1            (добавляется в сценарии, Part 1)
```

## Устройство Packet Tracer -> пространство имён

| Packet Tracer | netns | Интерфейсы (в Linux «/» в имени запрещён) |
|---|---|---|
| R1 | `R1` | `G0-0-0` = G0/0/0, `G0-0-1` = G0/0/1 |
| R3 | `R3` | `G0-0-0` = G0/0/0, `G0-0-1` = G0/0/1 |
| FIREWALL (ASA 5505) | `FIREWALL` | `VLAN1` inside, `VLAN2` outside, `VLAN3` dmz |
| S2 | `S2` | мост `br0`, порты `Fa0-1`, `Fa0-2` (номера портов условные) |
| S3 | `S3` | мост `br0`, порты `G0-1`, `Fa0-2` (номера портов условные) |
| Server-PT www.devasc-netacad.pka (DEVASC Server) | `DEVASC-Server` | `Fa0`; файлы HTTP: `/srv/DEVASC-Server/http` |
| Server-PT www.example.com (Example Server) | `Example-Server` | `Fa0` |
| облако Internet | `Internet` | `to-R1`, `to-R3`, `to-Example` |
| PC-A, PC-B | `PC-A`, `PC-B` | `Fa0` = FastEthernet0 |

## Шаги методички -> шаги сценария

| Методичка | Сценарий |
|---|---|
| Исходный файл .pka | `topo_devices`, `topo_interfaces`; ACL: `fw_acl_new` ... `fw_access_group` |
| Part 1 Step 1 (PC, кабели) | `add_pc_a` ... `s3_ports` |
| Part 1 Step 2 (IPv4, Check Results) | `pc_a_ip` ... `check_pc_a` |
| Part 2 c-e (ping с PC-B) | `ping_r3`, `ping_example`, `ping_devasc` (+ `trace_*`) |
| Part 3 Step 1 (index.html) | `http_service`, `http_files_before`, `index_html`, `http_files_after` |
| Part 3 Step 2 (Web Browser) | `curl_page`, `http_log`, снимок `browser_shot_1` |
| Part 4 Step 1 (show run) | `fw_interfaces`, `fw_show_run`, `fw_acl`, `fw_nat` |
| Part 4 Step 2 (no access-list, проверки) | `fw_no_icmp` ... `fw_counters` |

## Отличия от методички

- GUI Packet Tracer заменён командами: «поставить PC» = `ip netns add`, «кабель» = пара veth,
  IP Configuration = `ip address`/`ip route`, Command Prompt `ping` = `ping -c 4`, Web Browser = `curl -i`
  (плюс снимок страницы headless Chrome из PC-B: `files/pcb-web-browser-*.png`). Процента
  выполнения нет: вместо Check Results показаны имена устройств и ping шлюза с PC-A.
- ASA заменён iptables. `access-list OUTSIDE-DMZ ... permit icmp/tcp ... eq www` = правила цепочки
  `OUTSIDE-DMZ` (www = порт 80), неявный запрет = явное правило DROP в конце цепочки,
  `access-group ... in interface outside` = переход из FORWARD для `-i VLAN2`,
  `no access-list ...` = `iptables -D` с тем же содержимым правила, `show run` = `iptables-save`.
  ACL проверяется после DNAT по реальному адресу 192.168.2.3, как на ASA 8.3+.
  Счётчики iptables считают пакеты NEW-соединений (ответы проходят по правилу ESTABLISHED).
- Static NAT: ASA отвечает на ARP за 209.165.200.227; здесь это адрес /32 на VLAN2 и DNAT/SNAT.
  NAT, уровни безопасности и облако Internet (один маршрутизатор, маршруты к 209.165.200.224/29 и
  172.16.3.0/24) в методичке не показаны и восстановлены по смыслу.
- Шлюз DEVASC Server взят из Addressing Table как есть: 192.168.1.1 (вне его подсети). В Linux такой
  маршрут задаётся с `onlink`; ответы доходят, потому что FIREWALL отвечает на ARP за свой адрес
  192.168.1.1 и на VLAN3.
- Linux отвечает с начальным TTL 64 (в Packet Tracer 255 у маршрутизаторов, 128 у PC). STP на мостах
  выключен, поэтому повторять ping «до сходимости», как в методичке, обычно не требуется.
- Файлы сервера лежат в общей ФС (`/srv/DEVASC-Server/http`): netns разделяет только сетевой стек.
  Исходный `index.html` - заглушка из `prepare.sh`; новый файл задаёт шаг `write_file`.
- DNS не настраивается: в 5.4.6 его нет (появляется в 5.5.7). IPv6 отключён на устройствах
  из `prepare.sh`; на PC-A/PC-B виден только link-local fe80.
- В Part 2 методички нет нумерованных шагов (только a-e), в заголовках он обозначен как Step 1.
  Шаги с пометкой «доп.» (traceroute, журнал HTTP, NAT, порт 8080, счётчики) добавлены для отчёта.
- `prepare.sh` после самопроверки обнуляет счётчики FIREWALL и журнал HTTP, поэтому в протоколе
  видны только пакеты из шагов сценария. Служебные шаги `browser_shot_*` (снимки Chrome из PC-B)
  тоже отправляют HTTP-запросы: они входят в счётчики правила tcp/80 и в `files/DEVASC-Server-http.log`.

## Что проверить в результатах прогона

1. Лог шага «Подготовка стенда»: строка `OK: DEVASC-Server -> Example-Server`, без `WARNING`.
2. `ping_devasc` и `curl_page`: ответы от 209.165.200.227 (проверка шлюза `onlink`).
3. `trace_devasc`: хопы 172.16.3.1, 10.2.2.1, 10.1.1.2, 209.165.200.226, 209.165.200.227.
4. `ping_devasc_denied`: 100% потерь, код 1; `curl_page_after`: снова 200 OK; `curl_other_port`: код 28.
5. В `steps.json` нет `unexpected_exit`/`timeout`; в `files/` есть оба PNG (если Chrome не
   запустился в netns, снимков не будет, на протокол это не влияет).

## Снимок страницы в браузере

Служебные шаги `browser_shot_1/2` пытались снять страницу headless-браузером Chrome из пространства имён PC-B,
но Chrome на раннере отклонил загрузку (`net::ERR_BLOCKED_BY_CLIENT`), снимков нет. Страница проверялась
командой `curl` из PC-B (в протоколе), это равнозначно просмотру в веб-браузере Packet Tracer по содержимому.
