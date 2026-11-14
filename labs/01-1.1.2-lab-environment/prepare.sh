#!/usr/bin/env bash
# Подготовка стенда для лабораторной 1.1.2 (root, до записи, в протокол не попадает).
# Лабораторную ВМ уже собрал lab-env/setup-labvm.sh (предыдущий шаг CI); VirtualBox и образ
# DEVASC_VM.ova не используются. Здесь только то, что нужно шагам сценария.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"

# Копия сценария сборки ВМ в домашнем каталоге devasc, чтобы показать её командой cat.
install -d -o devasc -g devasc -m 0755 /home/devasc/lab-env
install -o devasc -g devasc -m 0755 "$REPO/lab-env/setup-labvm.sh" /home/devasc/lab-env/setup-labvm.sh

# Каталог лабораторных, как в ВМ DEVASC (его создаёт и setup-labvm.sh; повтор безопасен).
mkdir -p /home/devasc/labs/devnet-src
chown -R devasc:devasc /home/devasc/labs

# Имя хоста labvm должно разрешаться, иначе sudo пишет "unable to resolve host labvm".
# Docker обычно сам добавляет его в /etc/hosts; запись нужна только если его там нет.
grep -qw labvm /etc/hosts || echo "127.0.1.1 labvm" >> /etc/hosts || true

# sudo 1.8.31 (Ubuntu 20.04) в контейнере Docker без CAP_SYS_RESOURCE печатает при каждом вызове
# "sudo: setrlimit(RLIMIT_CORE): Operation not permitted" (в ВМ DEVASC этого нет). Параметр sudo.conf
# отключает только работу sudo с лимитом core-файлов; права sudo он не меняет.
grep -qs '^Set disable_coredump false' /etc/sudo.conf || echo 'Set disable_coredump false' >> /etc/sudo.conf
