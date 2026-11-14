#!/usr/bin/env bash
# Подготовка стенда для лабораторной 5.5.7 "Packet Tracer - Explore Network Protocols".
# Выполняется от root на ВМ раннера (Ubuntu 24.04) до записи, в протокол не попадает.
#
# Packet Tracer заменён сетевыми пространствами имён Linux: одно пространство на
# устройство PT (имя пространства = имя устройства), адреса из таблицы адресации.
# Здесь поднимается только то, что в файле .pka настроено заранее: топология, NAT и
# список доступа OUTSIDE-DMZ на FIREWALL, SSH на S2, SNMP на R3, DNS и веб-сервер
# Example Server, HTTP на DEVASC Server, файл sampleFile.txt на PC-A.
# Всё, что по методичке настраивает студент, выполняется в scenario.yml.
# Скрипт идемпотентен: при повторном запуске стенд пересоздаётся с нуля.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
LAB="$(cd "$(dirname "$0")" && pwd)"
export DEBIAN_FRONTEND=noninteractive

NSLIST="Internet R1 R3 FIREWALL S2 S3 Corporate PC-A PC-B DEVASC-Server Example-Server"
WORK=/home/devasc/labs/devnet-src/pt-protocols

echo "== Пакеты"
apt-get update -qq
apt-get install -y -qq dnsmasq-base chrony nginx snmpd snmp telnet busybox curl openssl \
  iptables iproute2 psmisc dnsutils python3-paramiko >/dev/null
apt-get install -y -qq python3-pyftpdlib python3-aiosmtpd >/dev/null 2>&1 || true
# проверяются именно используемые классы (старые pyftpdlib импортируют asynchat, которого нет в Python 3.12)
PYCHECK='from pyftpdlib.servers import ThreadedFTPServer; from pyftpdlib.handlers import FTPHandler
from pyftpdlib.authorizers import DummyAuthorizer; from aiosmtpd.controller import Controller; import paramiko'
python3 -c "$PYCHECK" 2>/dev/null || pip3 install -q --break-system-packages --upgrade pyftpdlib aiosmtpd
apt-get install -y -qq tnftp >/dev/null 2>&1 || apt-get install -y -qq ftp >/dev/null
busybox --list 2>/dev/null | grep -qx udhcpc || apt-get install -y -qq busybox-static >/dev/null
for c in dnsmasq chronyd chronyc nginx snmpd snmpget snmpwalk telnet ftp busybox curl iptables openssl ssh dig; do
  command -v "$c" >/dev/null || { echo "ERROR: command $c not found" >&2; exit 1; }
done
busybox --list | grep -qx udhcpc || { echo "ERROR: busybox has no udhcpc applet" >&2; exit 1; }
python3 -c "$PYCHECK"
id dnsmasq >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin dnsmasq
modprobe dummy 2>/dev/null || true

echo "== Очистка предыдущего запуска"
for ns in $NSLIST; do
  if [ -e "/run/netns/$ns" ]; then
    ip netns pids "$ns" 2>/dev/null | xargs -r kill -9 2>/dev/null || true
    ip netns del "$ns" 2>/dev/null || true
  fi
done
ip link del lab-a 2>/dev/null || true
rm -f /etc/dnsmasq.d/Corporate-dns.conf /etc/dnsmasq.d/Corporate-dhcp.conf /etc/chrony/Corporate-chrony.conf \
  /etc/labnet/Example-Server-email.ini /etc/labnet/Corporate-ftp.ini \
  /var/lib/misc/dnsmasq.leases /run/nginx-DEVASC-Server.pid /run/nginx-Example-Server.pid /run/snmpd-R3.pid \
  /run/chrony/Corporate.pid /run/chrony/Corporate.sock /run/labnet/S2-console.sock
rm -rf /var/log/pt-lab /var/spool/pt-mail /srv/labnet
ssh-keygen -R 192.168.1.4 -f /root/.ssh/known_hosts >/dev/null 2>&1 || true
mkdir -p /run/labnet /var/lib/labnet /var/log/pt-lab /opt/labnet /etc/labnet /etc/dnsmasq.d /etc/chrony

echo "== Программы стенда"
install -m 0755 "$LAB/src/s2_switch.py" "$LAB/src/email_server.py" "$LAB/src/ftp_server.py" /opt/labnet/
install -m 0644 "$REPO/tools/csr1kv_emulator/csr1kv_emulator.py" /opt/labnet/
install -m 0755 "$LAB/src/dhcp.sh" /opt/labnet/dhcp.sh
install -m 0755 "$LAB/src/pt_console.py" /usr/local/bin/pt-console
sed -i 's/\r$//' /opt/labnet/*.py /opt/labnet/dhcp.sh /usr/local/bin/pt-console

echo "== Пространства имён (устройства PT)"
for ns in $NSLIST; do
  ip netns add "$ns"
  # в методичке используется только IPv4
  ip netns exec "$ns" sysctl -qw net.ipv6.conf.all.disable_ipv6=1 net.ipv6.conf.default.disable_ipv6=1 || true
  ip -n "$ns" link set lo up
done

link() {  # link NS1 IF1 NS2 IF2 - кабель между устройствами
  ip link add lab-a type veth peer name lab-b
  ip link set lab-a netns "$1"
  ip link set lab-b netns "$3"
  ip -n "$1" link set lab-a name "$2"
  ip -n "$3" link set lab-b name "$4"
  ip -n "$1" link set "$2" up
  ip -n "$3" link set "$4" up
}
link Internet to-R1        R1 Gi0-0-1
link Internet to-R3        R3 Gi0-0-0
link Internet to-Example   Example-Server eth0
link R1 Gi0-0-0            FIREWALL vlan2
link FIREWALL vlan1        S2 to-FIREWALL
link FIREWALL vlan3        DEVASC-Server eth0
link S2 to-Corporate       Corporate eth0
link S2 to-PC-A            PC-A eth0
link R3 Gi0-0-1            S3 to-R3
link S3 to-PC-B            PC-B eth0

# Коммутаторы: мост Linux; у S2 интерфейс управления Vlan1 = сам мост с адресом 192.168.1.4
for sw in S2 S3; do
  ip -n "$sw" link add vlan1 type bridge
  ip -n "$sw" link set vlan1 up
done
for p in to-FIREWALL to-Corporate to-PC-A; do ip -n S2 link set "$p" master vlan1; done
for p in to-R3 to-PC-B; do ip -n S3 link set "$p" master vlan1; done

ip -n Internet addr add 10.1.1.1/30 dev to-R1
ip -n Internet addr add 10.2.2.1/30 dev to-R3
ip -n Internet addr add 64.100.0.1/24 dev to-Example
ip -n Internet route add 209.165.200.224/29 via 10.1.1.2
ip -n Internet route add 172.16.3.0/24 via 10.2.2.2

ip -n R1 addr add 209.165.200.225/29 dev Gi0-0-0
ip -n R1 addr add 10.1.1.2/30 dev Gi0-0-1
ip -n R1 route add default via 10.1.1.1

ip -n R3 addr add 10.2.2.2/30 dev Gi0-0-0
ip -n R3 addr add 172.16.3.1/24 dev Gi0-0-1
ip -n R3 route add default via 10.2.2.1
ip -n R3 link add Vlan1 type dummy 2>/dev/null || true   # третий интерфейс R3, выключен

ip -n FIREWALL addr add 192.168.1.1/24 dev vlan1
ip -n FIREWALL addr add 209.165.200.226/29 dev vlan2
ip -n FIREWALL addr add 209.165.200.227/29 dev vlan2      # адрес статического NAT DEVASC Server
ip -n FIREWALL addr add 192.168.2.1/24 dev vlan3
ip -n FIREWALL route add default via 209.165.200.225

ip -n S2 addr add 192.168.1.4/24 dev vlan1
ip -n S2 route add default via 192.168.1.1
ip -n Corporate addr add 192.168.1.3/24 dev eth0
ip -n Corporate route add default via 192.168.1.1
ip -n PC-A addr add 192.168.1.2/24 dev eth0                # статический адрес из 5.4.6 (до DHCP)
ip -n PC-A route add default via 192.168.1.1
ip -n PC-B addr add 172.16.3.2/24 dev eth0
ip -n PC-B route add default via 172.16.3.1
ip -n DEVASC-Server addr add 192.168.2.3/24 dev eth0
ip -n DEVASC-Server route add default via 192.168.2.1     # в таблице опечатка 192.168.1.1
ip -n Example-Server addr add 64.100.0.10/24 dev eth0
ip -n Example-Server route add default via 64.100.0.1

for ns in Internet R1 R3 FIREWALL; do ip netns exec "$ns" sysctl -qw net.ipv4.ip_forward=1; done
for ns in S2 S3 Corporate PC-A PC-B DEVASC-Server Example-Server; do
  ip netns exec "$ns" sysctl -qw net.ipv4.ip_forward=0
done

echo "== FIREWALL: зоны inside/outside/dmz, NAT, список доступа OUTSIDE-DMZ"
fw() { ip netns exec FIREWALL iptables "$@"; }
fw -P FORWARD DROP
fw -A FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
fw -A FORWARD -i vlan1 -o vlan2 -j ACCEPT
fw -A FORWARD -i vlan1 -o vlan3 -j ACCEPT
fw -A FORWARD -i vlan3 -o vlan2 -j ACCEPT
fw -N OUTSIDE-DMZ
fw -A OUTSIDE-DMZ -p icmp -d 192.168.2.3 -j ACCEPT
fw -A OUTSIDE-DMZ -p tcp -d 192.168.2.3 --dport 80 -j ACCEPT
fw -A OUTSIDE-DMZ -p tcp -d 192.168.2.3 --dport 443 -j ACCEPT
fw -A FORWARD -i vlan2 -j OUTSIDE-DMZ
fw -t nat -A PREROUTING -i vlan2 -d 209.165.200.227 -j DNAT --to-destination 192.168.2.3
fw -t nat -A POSTROUTING -o vlan2 -s 192.168.2.3 -j SNAT --to-source 209.165.200.227
fw -t nat -A POSTROUTING -o vlan2 -s 192.168.1.0/24 -j SNAT --to-source 209.165.200.226

echo "== Настройки ПК (nsswitch/hosts для пространств имён PC-A и PC-B)"
for pc in PC-A PC-B; do
  mkdir -p "/etc/netns/$pc"
  printf 'passwd: files\ngroup: files\nshadow: files\nhosts: files dns\nnetworks: files\nprotocols: files\nservices: files\n' \
    > "/etc/netns/$pc/nsswitch.conf"
  printf '127.0.0.1 localhost\n' > "/etc/netns/$pc/hosts"
  rm -f "/etc/netns/$pc/resolv.conf"
done

echo "== S2: SSH (administrator/cisco), enable secret cisco, консоль"
ip netns exec S2 setsid -f python3 /opt/labnet/s2_switch.py --host 192.168.1.4 --hostname S2 \
  --username administrator --password cisco --enable-secret cisco \
  --host-key /var/lib/labnet/S2_host_key --console /run/labnet/S2-console.sock \
  --log /var/log/pt-lab/S2.log >/var/log/pt-lab/S2.out 2>&1 </dev/null

echo "== R3: SNMP-агент (community read / write)"
cat > /etc/snmp/R3-snmpd.conf <<'EOF'
# R3: SNMP-агент net-snmp (в Packet Tracer на R3 заранее созданы community read и write)
agentAddress udp:172.16.3.1:161,udp:10.2.2.2:161
rocommunity read
rwcommunity write
sysName R3
sysLocation R3, LAN 172.16.3.0/24
include_ifmib_iface_prefix Gi Vlan
EOF
ip netns exec R3 /usr/sbin/snmpd -C -c /etc/snmp/R3-snmpd.conf -p /run/snmpd-R3.pid -Lf /var/log/pt-lab/snmpd-R3.log

echo "== Example Server: DNS и веб-сервер www.example.com"
cat > /etc/dnsmasq.d/Example-Server-dns.conf <<'EOF'
# Example Server (www.example.com): DNS-сервер, которым пользуется PC-B (в PT уже работает)
port=53
listen-address=64.100.0.10
bind-interfaces
no-resolv
no-hosts
host-record=www.example.com,64.100.0.10
host-record=www.devasc-netacad.pka,209.165.200.227
log-queries
pid-file
EOF
ip netns exec Example-Server dnsmasq -C /etc/dnsmasq.d/Example-Server-dns.conf

mkdir -p /srv/labnet/Example-Server/www /srv/labnet/DEVASC-Server/www
cat > /srv/labnet/Example-Server/www/index.html <<'EOF'
<!DOCTYPE html>
<html>
<head><title>www.example.com</title></head>
<body>
<h1>www.example.com</h1>
<p>Example Server, 64.100.0.10</p>
</body>
</html>
EOF
cat > /srv/labnet/DEVASC-Server/www/index.html <<'EOF'
<!DOCTYPE html>
<html>
<head><title>DevNet Associate</title></head>
<body>
<h1>DevNet Associate</h1>
<p>www.devasc-netacad.pka (DEVASC Server, 192.168.2.3 / 209.165.200.227)</p>
</body>
</html>
EOF
chmod -R a+rX /srv/labnet

nginx_conf() {  # nginx_conf DEVICE LISTEN NAME
  cat <<EOF
# $1 ($3): веб-сервер nginx. В Packet Tracer: Services > HTTP, HTTP On, HTTPS Off
user www-data;
worker_processes 1;
pid /run/nginx-$1.pid;
error_log /var/log/pt-lab/nginx-$1.error.log;
events {
    worker_connections 64;
}
http {
    include /etc/nginx/mime.types;
    access_log /var/log/pt-lab/nginx-$1.access.log;
    server {
        listen $2:80;
        server_name $3;
        root /srv/labnet/$1/www;
        index index.html;
    }
}
EOF
}
nginx_conf Example-Server 64.100.0.10 www.example.com > /etc/nginx/Example-Server.conf
nginx_conf DEVASC-Server 192.168.2.3 www.devasc-netacad.pka > /etc/nginx/DEVASC-Server.conf
ip netns exec Example-Server nginx -c /etc/nginx/Example-Server.conf
ip netns exec DEVASC-Server nginx -c /etc/nginx/DEVASC-Server.conf

echo "== Corporate: каталог FTP-сервера (файлы-заглушки с именами и размерами как в PT)"
mkdir -p /srv/labnet/Corporate/ftp
for f in asa842-k8.bin:5571584 asa923-k8.bin:30468096 c1841-advipservicesk9-mz.124-15.T1.bin:33591768 \
         c1841-ipbase-mz.123-14.T7.bin:13832032; do
  truncate -s "${f##*:}" "/srv/labnet/Corporate/ftp/${f%%:*}"
done

echo "== Рабочий каталог студента (диски PC-A и PC-B)"
rm -rf "$WORK"
mkdir -p "$WORK/PC-A" "$WORK/PC-B" "$WORK/DEVASC-Server"
printf 'PC-A sample file for FTP.\n' > "$WORK/PC-A/sampleFile.txt"   # 26 байт, как в PT
chown -R devasc:devasc /home/devasc/labs

echo "== Проверка стенда"
wait_for() {  # wait_for ОПИСАНИЕ КОМАНДА...
  local what="$1"; shift
  for _ in $(seq 1 30); do
    if "$@" >/dev/null 2>&1; then echo "  ok: $what"; return 0; fi
    sleep 1
  done
  echo "  WARNING: $what - не готово" >&2
  return 1
}
wait_for "S2 SSH 192.168.1.4:22" ip netns exec S2 bash -c 'exec 3<>/dev/tcp/192.168.1.4/22' || cat /var/log/pt-lab/S2.out >&2
wait_for "S2 console" test -S /run/labnet/S2-console.sock || true
wait_for "PC-B -> R3" ip netns exec PC-B ping -c1 -W2 172.16.3.1 || true
wait_for "PC-B -> Example Server" ip netns exec PC-B ping -c1 -W2 64.100.0.10 || true
wait_for "PC-B -> DEVASC Server (NAT)" ip netns exec PC-B ping -c1 -W2 209.165.200.227 || true
wait_for "PC-A -> Example Server" ip netns exec PC-A ping -c1 -W2 64.100.0.10 || true
wait_for "HTTP DEVASC Server" ip netns exec PC-B curl -sf -m5 -o /dev/null http://209.165.200.227/ || true
wait_for "HTTP Example Server" ip netns exec PC-B curl -sf -m5 -o /dev/null http://64.100.0.10/ || true
wait_for "DNS Example Server" ip netns exec PC-B dig +short +time=2 +tries=1 @64.100.0.10 www.example.com || true
wait_for "SNMP R3" ip netns exec PC-B snmpget -v2c -c read -t 2 -r 1 172.16.3.1 1.3.6.1.2.1.1.5.0 || true
ip netns list
