#!/usr/bin/env bash
# Подготовка ВМ раннера (Ubuntu 24.04) к лабораторной 7.4.8. Выполняется от root.
# Воспроизводит то, что в ВМ DEVASC есть "из коробки": интерфейс dummy0 с адресами
# 192.0.2.1-5, пользователь devasc с паролем Cisco123!, установленные sshd и sshpass.
set -euo pipefail

# Интерфейс dummy0 с адресами из документационной сети 192.0.2.0/24 (RFC 5737)
modprobe dummy 2>/dev/null || true
ip link add dummy0 type dummy 2>/dev/null || true
ip link set dummy0 up
for i in 1 2 3 4 5; do ip addr add "192.0.2.${i}/32" dev dummy0 2>/dev/null || true; done

# Пароль devasc из методички. Раннер одноразовый и недоступен из интернета.
echo 'devasc:Cisco123!' | chpasswd

# sshd: вход по паролю (в образах облака он выключен), до шага методички сервис остановлен
mkdir -p /etc/ssh/sshd_config.d
printf 'PasswordAuthentication yes\nKbdInteractiveAuthentication yes\n' > /etc/ssh/sshd_config.d/00-devasc-lab.conf
systemctl stop ssh.socket ssh.service 2>/dev/null || true

# В образе раннера заранее стоят apache2/nginx; удаляем их, чтобы плейбук реально установил Apache
systemctl stop nginx apache2 2>/dev/null || true
systemctl disable nginx 2>/dev/null || true
apt-get purge -y -qq 'apache2*' >/dev/null 2>&1 || true
rm -rf /etc/apache2 /var/www/html/index.html

# Исходный каталог лабораторной (как в devnet-src)
D=/home/devasc/labs/devnet-src/ansible/ansible-apache
mkdir -p "$D"
: > "$D/hosts"
echo "# Add to this file for the Ansible lab" > "$D/ansible.cfg"
chown -R devasc:devasc /home/devasc/labs
