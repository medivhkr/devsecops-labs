#!/usr/bin/env bash
# Подготовка стенда для лабораторной 4.9.2 (выполняется от root, в протокол не попадает).
# В ВМ DEVASC уже есть Python 3 с модулем requests и каталог ~/labs/devnet-src/mapquest.
# Ключ MapQuest берётся только из переменной окружения MAPQUEST_KEY (секрет репозитория,
# его передаёт шаг «Подготовка стенда» в _run-lab.yml) и сохраняется в /home/devasc/.mapquest_env
# (владелец devasc, права 600); scenario.yml подключает файл в shell_init. Значение нигде не выводится.
set -euo pipefail

# requests (есть в ВМ DEVASC), curl и jq (просмотр JSON вместо Chromium + JSONView)
need=""
python3 -c "import requests" 2>/dev/null || need="$need python3-requests"
command -v curl >/dev/null 2>&1 || need="$need curl"
command -v jq >/dev/null 2>&1 || need="$need jq"
if [ -n "$need" ]; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  # shellcheck disable=SC2086  # список пакетов намеренно разбивается на слова
  apt-get install -y -qq $need >/dev/null
fi
python3 -c "import requests; print('requests', requests.__version__)"

# Рабочий каталог лабораторной (в ВМ DEVASC он уже существует)
mkdir -p /home/devasc/labs/devnet-src/mapquest
chown -R devasc:devasc /home/devasc/labs

# Ключ API: из переменной окружения в файл с правами 600, без вывода значения
ENV_FILE=/home/devasc/.mapquest_env
KEY="$(printf '%s' "${MAPQUEST_KEY:-}" | tr -d '[:space:]')"
case "$KEY" in
  "")
    echo "ВНИМАНИЕ: MAPQUEST_KEY не задан (секрет репозитория), запросы к MapQuest API завершатся ошибкой" >&2
    ;;
  *\'*)
    echo "ВНИМАНИЕ: MAPQUEST_KEY содержит одинарную кавычку (это не ключ MapQuest), файл не записан" >&2
    ;;
  *)
    ( umask 077 && printf "export MAPQUEST_KEY='%s'\n" "$KEY" > "$ENV_FILE" )
    chown devasc:devasc "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "MAPQUEST_KEY записан в $ENV_FILE (владелец devasc, права 600)"
    ;;
esac
unset KEY

# Диагностика для первого прогона: доступность API (запрос без ключа, тело ответа не выводится)
curl -s -o /dev/null --max-time 20 -w 'www.mapquestapi.com: HTTP %{http_code}\n' \
  https://www.mapquestapi.com/directions/v2/route || echo "ВНИМАНИЕ: www.mapquestapi.com недоступен" >&2
