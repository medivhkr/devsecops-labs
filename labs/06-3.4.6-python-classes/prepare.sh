#!/usr/bin/env bash
# Подготовка стенда для лабораторной 3.4.6 (root, в протокол не попадает).
# В ВМ DEVASC каталог ~/labs/devnet-src/python уже есть, в контейнере его нужно создать.
# Пакеты не нужны: работа использует только python3 из lab-env/setup-labvm.sh.
set -euo pipefail

D=/home/devasc/labs/devnet-src/python
mkdir -p "$D"
chown -R devasc:devasc /home/devasc/labs
