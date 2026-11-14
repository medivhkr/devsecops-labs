#!/usr/bin/env bash
# Подготовка стенда для 5.4.6 Packet Tracer - Explore a Simple Network (ВМ Ubuntu 24.04).
# Выполняется от root до записи протокола, в протокол не попадает.
#
# Packet Tracer недоступен, поэтому топология файла .pka воспроизводится средствами Linux:
#   устройство Packet Tracer -> сетевое пространство имён (ip netns) с тем же именем;
#   кабель                   -> пара veth (имена портов: G0/0/0 -> G0-0-0, "/" в Linux запрещён);
#   коммутатор S2 / S3       -> мост Linux br0 внутри пространства имён S2 / S3;
#   ASA FIREWALL             -> маршрутизация + iptables (src/FIREWALL.rules: static NAT, PAT,
#                               уровни безопасности; сам ACL OUTSIDE-DMZ создаёт сценарий);
#   служба HTTP Server-PT    -> python3 -m http.server в пространстве имён DEVASC-Server.
# PC-A и PC-B здесь НЕ создаются: их добавляет сценарий (Part 1), как в методичке.
# Скрипт идемпотентен: стенд предыдущего запуска удаляется и строится заново.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
LAB="$(cd "$(dirname "$0")" && pwd)"
export DEBIAN_FRONTEND=noninteractive
echo "repo: $REPO"

WWW=/srv/DEVASC-Server/http
HTTP_LOG=/var/log/DEVASC-Server-http.log
UNIT=pt546-devasc-http
ALL_NS="PC-A PC-B R1 R3 FIREWALL Internet S2 S3 DEVASC-Server Example-Server"

echo "== Пакеты"
PKGS="iproute2 iptables iputils-ping traceroute curl python3"
if ! apt-get install -y -qq $PKGS >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq $PKGS >/dev/null
fi
# traceroute Дмитрия Бутского (ключи -n -I); inetutils-traceroute, если он есть, не подходит
update-alternatives --set traceroute /usr/bin/traceroute.db >/dev/null 2>&1 || true

echo "== Очистка стенда предыдущего запуска"
systemctl stop "$UNIT" >/dev/null 2>&1 || true
systemctl reset-failed "$UNIT" >/dev/null 2>&1 || true
pkill -f "http.server 80 --bind 192.168.2.3" >/dev/null 2>&1 || true
for ns in $ALL_NS; do
  if [ -e "/run/netns/$ns" ]; then
    pids="$(ip netns pids "$ns" 2>/dev/null || true)"
    for pid in $pids; do kill "$pid" 2>/dev/null || true; done
    ip netns del "$ns" || true
  fi
done

mkns() {   # mkns УСТРОЙСТВО ip_forward(0|1)
  ip netns add "$1"
  ip -n "$1" link set lo up
  ip netns exec "$1" sysctl -qw net.ipv4.ip_forward="$2"
  # IPv6 в 5.4.6 не используется: отключаем, чтобы в выводе были только адреса из Addressing Table
  ip netns exec "$1" sysctl -qw net.ipv6.conf.all.disable_ipv6=1 \
    net.ipv6.conf.default.disable_ipv6=1 >/dev/null 2>&1 || true
}

cable() {  # cable УСТР1 ПОРТ1 УСТР2 ПОРТ2: пара veth сразу между двумя пространствами имён
  ip link add "$2" netns "$1" type veth peer name "$4" netns "$3"
  ip -n "$1" link set "$2" up
  ip -n "$3" link set "$4" up
}

echo "== Устройства (network namespaces)"
for ns in R1 R3 FIREWALL Internet; do mkns "$ns" 1; done
for ns in S2 S3 DEVASC-Server Example-Server; do mkns "$ns" 0; done

echo "== Коммутаторы S2 и S3"
for sw in S2 S3; do
  ip -n "$sw" link add br0 type bridge
  ip -n "$sw" link set br0 up
done

echo "== Кабели"
cable FIREWALL VLAN1 S2 Fa0-1
ip -n S2 link set Fa0-1 master br0
cable FIREWALL VLAN2 R1 G0-0-0
cable FIREWALL VLAN3 DEVASC-Server Fa0
cable R1 G0-0-1 Internet to-R1
cable R3 G0-0-0 Internet to-R3
cable R3 G0-0-1 S3 G0-1
ip -n S3 link set G0-1 master br0
cable Example-Server Fa0 Internet to-Example

echo "== Адресация (Addressing Table)"
# R1
ip -n R1 addr add 209.165.200.225/29 dev G0-0-0
ip -n R1 addr add 10.1.1.2/30 dev G0-0-1
ip -n R1 route add default via 10.1.1.1
# Облако Internet (в методичке не показано, восстановлено по смыслу): один транзитный маршрутизатор 10.1.1.1 / 10.2.2.1 / 64.100.0.1
ip -n Internet addr add 10.1.1.1/30 dev to-R1
ip -n Internet addr add 10.2.2.1/30 dev to-R3
ip -n Internet addr add 64.100.0.1/24 dev to-Example
ip -n Internet route add 209.165.200.224/29 via 10.1.1.2
ip -n Internet route add 172.16.3.0/24 via 10.2.2.2
# R3
ip -n R3 addr add 10.2.2.2/30 dev G0-0-0
ip -n R3 addr add 172.16.3.1/24 dev G0-0-1
ip -n R3 route add default via 10.2.2.1
# FIREWALL: VLAN1 = inside, VLAN2 = outside, VLAN3 = dmz
ip -n FIREWALL addr add 192.168.1.1/24 dev VLAN1
ip -n FIREWALL addr add 209.165.200.226/29 dev VLAN2
# Адрес static NAT сервера DEVASC. ASA отвечает на ARP за него (proxy ARP); здесь это адрес /32
# на VLAN2, а пакеты к нему правило DNAT (src/FIREWALL.rules) перенаправляет на 192.168.2.3.
ip -n FIREWALL addr add 209.165.200.227/32 dev VLAN2
ip -n FIREWALL addr add 192.168.2.1/24 dev VLAN3
ip -n FIREWALL route add default via 209.165.200.225
ip -n FIREWALL link set VLAN1 alias inside
ip -n FIREWALL link set VLAN2 alias outside
ip -n FIREWALL link set VLAN3 alias dmz
# Шлюз DEVASC Server (ниже) - 192.168.1.1, адрес FIREWALL на VLAN1. FIREWALL должен отвечать
# на ARP-запрос о нём, пришедший на VLAN3 (arp_ignore=0, значение ядра по умолчанию).
ip netns exec FIREWALL sysctl -qw net.ipv4.conf.all.arp_ignore=0 net.ipv4.conf.VLAN3.arp_ignore=0
# DEVASC Server (Server-PT www.devasc-netacad.pka)
ip -n DEVASC-Server addr add 192.168.2.3/24 dev Fa0
# Шлюз как в Addressing Table: 192.168.1.1 вне подсети 192.168.2.0/24, поэтому нужен onlink
ip -n DEVASC-Server route add default via 192.168.1.1 dev Fa0 onlink
# Example Server (Server-PT www.example.com)
ip -n Example-Server addr add 64.100.0.10/24 dev Fa0
ip -n Example-Server route add default via 64.100.0.1

echo "== FIREWALL: базовые правила iptables (NAT и уровни безопасности ASA)"
ip netns exec FIREWALL iptables-restore < "$LAB/src/FIREWALL.rules"

echo "== DEVASC Server: служба HTTP (в Server-PT включена по умолчанию)"
mkdir -p "$WWW"
cat > "$WWW/index.html" <<'EOF'
<html>
<center><font size='+2' color='blue'>www.devasc-netacad.pka</font></center>
<hr>Default page of the DEVASC Server HTTP service.
</html>
EOF
chmod 755 /srv/DEVASC-Server "$WWW"
chmod 644 "$WWW/index.html"
: > "$HTTP_LOG"
chmod 644 "$HTTP_LOG"
if ! systemd-run --quiet --unit "$UNIT" \
    --property NetworkNamespacePath=/run/netns/DEVASC-Server \
    --property StandardOutput=append:"$HTTP_LOG" \
    --property StandardError=append:"$HTTP_LOG" \
    /usr/bin/python3 -u -m http.server 80 --bind 192.168.2.3 --directory "$WWW"; then
  echo "systemd-run failed, starting the HTTP service with nohup"
  setsid nohup ip netns exec DEVASC-Server python3 -u -m http.server 80 --bind 192.168.2.3 \
    --directory "$WWW" >>"$HTTP_LOG" 2>&1 </dev/null &
fi
ready=""
for _ in $(seq 1 30); do
  listen="$(ip netns exec DEVASC-Server ss -ltn 2>/dev/null || true)"
  case "$listen" in *"192.168.2.3:80 "*) ready=1; break ;; esac
  sleep 1
done
if [ -z "$ready" ]; then
  echo "HTTP service in DEVASC-Server did not start" >&2
  systemctl status "$UNIT" --no-pager >&2 || true
  cat "$HTTP_LOG" >&2 || true
  exit 1
fi

echo "== Самопроверка (вне протокола)"
# ACL OUTSIDE-DMZ создаёт сценарий, поэтому снаружи к серверу пока нельзя (так и должно быть).
# Проверяется обратный путь DMZ -> outside: шлюз 192.168.1.1 (onlink), static NAT, R1, Internet.
if ip netns exec DEVASC-Server ping -c 2 -W 2 64.100.0.10 >/dev/null 2>&1 &&
   ip netns exec DEVASC-Server curl -s -o /dev/null -m 5 http://192.168.2.3/; then
  echo "OK: DEVASC-Server -> Example-Server (ICMP), HTTP service answers"
else
  echo "WARNING: self-check failed, diagnostics:" >&2
  ip -all netns exec ip -br address >&2 || true
  ip -all netns exec ip route >&2 || true
  ip netns exec DEVASC-Server ip neigh >&2 || true
  ip netns exec FIREWALL ip neigh >&2 || true
  ip netns exec FIREWALL iptables-save -c >&2 || true
fi
# Счётчики правил и журнал HTTP обнуляются: в протоколе видны только пакеты из шагов сценария
ip netns exec FIREWALL iptables -Z
ip netns exec FIREWALL iptables -t nat -Z
: > "$HTTP_LOG"

echo "== Исходная топология (PC-A и PC-B добавляет сценарий)"
ip netns list
