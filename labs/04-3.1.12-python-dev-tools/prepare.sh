#!/usr/bin/env bash
# Подготовка стенда для лабораторной 3.1.12 (выполняется от root, в протокол не попадает).
# В ВМ DEVASC каталог ~/labs/devnet-src/python есть до начала работы, а окружения devfun,
# devnew и файл requirements.txt студент создаёт сам по ходу лабораторной.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

# python3 -m venv требует пакет python3-venv (его ставит lab-env/setup-labvm.sh; здесь только проверка)
if ! dpkg -s python3-venv >/dev/null 2>&1; then
  apt-get install -y -qq python3-venv >/dev/null
fi

D=/home/devasc/labs/devnet-src/python
mkdir -p "$D"
# Повторный запуск на том же стенде: убрать результаты прошлого прогона и кэш pip пользователя,
# чтобы первая установка requests снова скачивала пакеты с PyPI, а вторая брала их из кэша.
rm -rf "$D/devfun" "$D/devnew" "$D/requirements.txt" /home/devasc/.cache/pip
chown -R devasc:devasc /home/devasc/labs
