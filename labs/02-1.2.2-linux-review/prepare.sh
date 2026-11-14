#!/usr/bin/env bash
# Подготовка ВМ раннера (Ubuntu 24.04, env: vm) к лабораторной 1.2.2 «Linux Review».
# Выполняется от root до записи, в протокол не попадает. Воссоздаёт то, что в ВМ DEVASC
# есть «из коробки» (домашний каталог с ярлыками, учётная запись devasc, dummy0, man),
# и делает apt предсказуемым для записи: настоящие запросы [Y/n], но без диалогов.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export DEBIAN_FRONTEND=noninteractive
U=devasc
H="/home/$U"

echo "== Учётная запись devasc: полное имя DEVASC и пароль Cisco123!, как в ВМ DEVASC"
usermod -c 'DEVASC,,,' "$U"
echo "$U:Cisco123!" | chpasswd

echo "== Локаль en_US.UTF-8 (как в ВМ DEVASC: порядок сортировки ls, формат date)"
if ! locale -a 2>/dev/null | grep -qix 'en_US.utf8'; then
  apt-get install -y -qq locales >/dev/null
  mkdir -p /var/lib/locales/supported.d
  echo 'en_US.UTF-8 UTF-8' > /var/lib/locales/supported.d/labrun-en
  if [ -f /etc/locale.gen ]; then sed -i 's/^# *\(en_US\.UTF-8 UTF-8\)/\1/' /etc/locale.gen; fi
  locale-gen en_US.UTF-8 >/dev/null || true
fi
locale -a 2>/dev/null | grep -ix 'en_US.utf8' || echo "WARNING: en_US.UTF-8 locale is missing" >&2

echo "== Справочные страницы man (ls, passwd)"
rm -f /etc/dpkg/dpkg.cfg.d/excludes      # есть только в «минимизированных» образах
rm -f /var/lib/man-db/auto-update        # не пересобирать индекс mandb: для man он не нужен
apt-get install -y -qq man-db >/dev/null || echo "WARNING: man-db was not installed" >&2
if [ "$(dpkg-divert --truename /usr/bin/man)" = "/usr/bin/man.REAL" ]; then
  rm -f /usr/bin/man
  dpkg-divert --quiet --remove --rename /usr/bin/man
fi
if ! man -w ls >/dev/null 2>&1 || ! man -w passwd >/dev/null 2>&1; then
  apt-get install -y -qq --reinstall coreutils passwd >/dev/null || echo "WARNING: reinstall failed" >&2
fi
man -w ls passwd || echo "WARNING: man pages for ls/passwd not found" >&2

echo "== Домашний каталог как в ВМ DEVASC: стандартные папки и ярлыки на рабочем столе"
for d in Desktop Documents Downloads Music Pictures Public Templates Videos snap; do
  install -d -o "$U" -g "$U" -m 0755 "$H/$d"
done
install -m 0755 -o "$U" -g "$U" -t "$H/Desktop" "$HERE"/src/Desktop/*.desktop
# следы предыдущего прогона (идемпотентность)
rm -f "$H/Desktop/myfile.sh" "$H"/Documents/myfile*.sh "$H/linux.txt" "$H/linux2.txt" "$H/linux3.txt"

echo "== Интерфейс dummy0 с адресами 192.0.2.1-5/32, как в ВМ DEVASC"
modprobe dummy 2>/dev/null || true
ip link add dummy0 type dummy 2>/dev/null || true
ip link set dummy0 up 2>/dev/null || true
for i in 1 2 3 4 5; do ip addr add "192.0.2.${i}/32" dev dummy0 2>/dev/null || true; done

echo "== Устройство локальной сети 192.168.1.1: netns lan-router, связь с ВМ через veth lan0"
setup_lan() {
  [ -e /run/netns/lan-router ] || ip netns add lan-router || return 1
  if ! ip link show lan0 >/dev/null 2>&1; then
    ip link add lan0 type veth peer name lan0-peer || return 1
    ip link set lan0-peer netns lan-router || return 1
    ip -n lan-router link set lan0-peer name eth0 || return 1
  fi
  ip addr replace 192.168.1.10/24 dev lan0 &&
    ip link set lan0 up &&
    ip -n lan-router addr replace 192.168.1.1/24 dev eth0 &&
    ip -n lan-router link set lo up &&
    ip -n lan-router link set eth0 up
}
setup_lan || echo "WARNING: netns lan-router was not set up" >&2
ping -c 1 -W 2 192.168.1.1 >/dev/null && echo "192.168.1.1 answers" || echo "WARNING: 192.168.1.1 does not answer" >&2

echo "== apt: запросы [Y/n] как в обычной ВМ, без диалогов debconf, needrestart и conffile"
# В образе раннера GitHub включён APT::Get::Assume-Yes; убираем, чтобы запросы были настоящими.
for f in /etc/apt/apt.conf /etc/apt/apt.conf.d/*; do
  [ -f "$f" ] || continue
  if grep -qi 'Assume-Yes' "$f"; then sed -i '/[Aa]ssume-[Yy]es/d' "$f"; fi
done
cat > /etc/apt/apt.conf.d/90labrun <<'EOF'
// lab 1.2.2: dpkg keeps existing conffiles without asking; plain (non-fancy) progress output
Dpkg::Options { "--force-confdef"; "--force-confold"; };
Dpkg::Progress-Fancy "0";
EOF
echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections || echo "WARNING: debconf" >&2
if [ -d /etc/needrestart ]; then
  mkdir -p /etc/needrestart/conf.d
  cat > /etc/needrestart/conf.d/90-labrun.conf <<'EOF'
# lab 1.2.2: only list outdated services, never restart them, no kernel/microcode dialogs
$nrconf{restart} = 'l';
$nrconf{kernelhints} = 0;
$nrconf{ucodehints} = 0;
EOF
fi
apt-get purge -y -qq apt-listchanges >/dev/null 2>&1 || true

echo "== speedtest-cli не установлен: его ставит сам студент (Part 5 Step 4c)"
apt-get purge -y -qq speedtest-cli >/dev/null 2>&1 || true

echo "== Готово"
getent passwd "$U"
ls -la "$H" "$H/Desktop"
ip -brief address
