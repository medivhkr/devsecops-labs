#!/usr/bin/env bash
# Подготовка стенда для лабораторной 3.5.7 (root, в протокол не попадает).
# Воспроизводит каталог ~/labs/devnet-src/unittest из ВМ DEVASC: файл с данными test_data.py
# и две заготовки с одной строкой комментария, в которые студент вписывает код.
# Пакеты не нужны: unittest входит в стандартную библиотеку Python 3.8 (ставится setup-labvm.sh).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
D=/home/devasc/labs/devnet-src/unittest

mkdir -p "$D"
install -m 0644 "$HERE/src/test_data.py" "$D/test_data.py"
printf '# Fill the Python code in this file\n' > "$D/recursive_json_search.py"
printf '# Fill the Python code in this file\n' > "$D/test_json_search.py"
chmod 0644 "$D/recursive_json_search.py" "$D/test_json_search.py"
rm -rf "$D/__pycache__"
chown -R devasc:devasc /home/devasc/labs

python3 --version
ls -l "$D"
