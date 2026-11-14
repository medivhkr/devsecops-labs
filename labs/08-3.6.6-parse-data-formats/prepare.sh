#!/usr/bin/env bash
# Подготовка стенда для лабораторной 3.6.6 (выполняется от root, в протокол не попадает).
# В ВМ DEVASC каталог ~/labs/devnet-src/parsing уже содержит файлы данных myfile.xml,
# myfile.json, myfile.yaml и заготовки parsexml.py, parsejson.py, parseyaml.py.
# Здесь каталог воссоздаётся из src/parsing (содержимое взято из текста методички).
# Код скриптов студент пишет сам: шаги write_file в scenario.yml.
# PyYAML на стенде из пакета python3-yaml (ставит lab-env/setup-labvm.sh), методичка ничего не ставит.
set -euo pipefail
LAB_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$LAB_DIR/src/parsing"
D=/home/devasc/labs/devnet-src/parsing

mkdir -p "$D"
for f in myfile.xml myfile.json myfile.yaml parsexml.py parsejson.py parseyaml.py; do
  install -m 0644 "$SRC/$f" "$D/$f"
done
chown -R devasc:devasc /home/devasc/labs
