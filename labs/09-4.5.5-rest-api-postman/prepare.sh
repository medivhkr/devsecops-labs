#!/usr/bin/env bash
# Подготовка стенда для лабораторной 4.5.5 (выполняется от root до записи, в протокол не попадает).
# Воспроизводит то, что в ВМ DEVASC есть "из коробки": симулятор School Library API на
# http://library.demo.local (порт 80), библиотеки requests и Faker, файл add100RandomBooks.py.
# Симулятор - собственная переписанная реализация (src/school_library_sim.py), а не код Cisco.
# Вместо Postman (GUI) ставится Newman - официальный CLI-запуск коллекций Postman.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
LAB="$REPO/labs/09-4.5.5-rest-api-postman"
export DEBIAN_FRONTEND=noninteractive

retry() {  # retry <попытки> <команда...>
  local attempts=$1 i
  shift
  for i in $(seq 1 "$attempts"); do
    if "$@"; then return 0; fi
    echo "attempt $i/$attempts failed: $*" >&2
    sleep 5
  done
  return 1
}

nodesource_setup() {
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
}

node_tarball() {  # запасной вариант: официальный архив Node.js 20 с nodejs.org (с проверкой SHA-256)
  local base=https://nodejs.org/dist/latest-v20.x name tmp
  name="$(curl -fsSL "$base/SHASUMS256.txt" | grep -oE 'node-v20\.[0-9]+\.[0-9]+-linux-x64\.tar\.gz' | head -n 1)"
  [ -n "$name" ] || return 1
  tmp="$(mktemp -d)"
  curl -fsSL -o "$tmp/$name" "$base/$name" || return 1
  (cd "$tmp" && curl -fsSL "$base/SHASUMS256.txt" | grep " $name\$" | sha256sum -c -) || return 1
  tar -xzf "$tmp/$name" -C /usr/local --strip-components=1 --no-same-owner
  rm -rf "$tmp"
}

echo "== Python: requests и Faker (в ВМ DEVASC предустановлены)"
apt-get install -y -qq python3-requests >/dev/null \
  || { apt-get update -qq && apt-get install -y -qq python3-requests >/dev/null; }
PIP_FLAGS=""
if ls /usr/lib/python3*/EXTERNALLY-MANAGED >/dev/null 2>&1; then PIP_FLAGS="--break-system-packages"; fi
retry 3 python3 -m pip install -q $PIP_FLAGS Faker
python3 -c "import faker, requests; print('Faker', faker.VERSION, '/ requests', requests.__version__)"

echo "== Node.js 20 (NodeSource) и Newman"
if ! node --version 2>/dev/null | grep -q '^v20\.'; then
  if retry 3 nodesource_setup; then
    apt-get install -y -qq nodejs >/dev/null || true
  fi
fi
if ! node --version 2>/dev/null | grep -q '^v20\.'; then
  echo "NodeSource did not give Node.js 20, using the nodejs.org archive" >&2
  retry 3 node_tarball
fi
node --version | grep -q '^v20\.' || { echo "Node.js 20 is not installed" >&2; exit 1; }
if ! newman --version >/dev/null 2>&1; then
  retry 3 npm install -g --no-fund --no-audit --loglevel=error newman@6
fi
echo "node $(node --version), npm $(npm --version), newman $(newman --version)"

echo "== Имя library.demo.local -> 127.0.0.1"
if ! grep -qE '^127\.0\.0\.1[[:space:]]+library\.demo\.local([[:space:]]|$)' /etc/hosts; then
  echo "127.0.0.1 library.demo.local" >> /etc/hosts
fi

echo "== Симулятор School Library API на 127.0.0.1:80"
install -d -m 0755 /opt/school-library-sim
install -m 0644 "$LAB/src/school_library_sim.py" /opt/school-library-sim/school_library_sim.py
if pkill -f school_library_sim.py; then
  for i in $(seq 1 20); do pgrep -f school_library_sim.py >/dev/null || break; sleep 0.5; done
fi
nohup python3 -u /opt/school-library-sim/school_library_sim.py --host 127.0.0.1 --port 80 \
  >/var/log/school-library-sim.log 2>&1 </dev/null &
for i in $(seq 1 30); do
  # проверка по /api/v1/swagger.json: GET /books ограничен по частоте, его не трогаем
  if curl -fsS -o /dev/null http://library.demo.local/api/v1/swagger.json 2>/dev/null; then break; fi
  sleep 1
done
if ! curl -fsS -o /dev/null http://library.demo.local/api/v1/swagger.json; then
  echo "simulator did not start" >&2
  cat /var/log/school-library-sim.log >&2
  exit 1
fi
head -n 1 /var/log/school-library-sim.log

echo "== Файлы лабораторной, как в ВМ DEVASC, и коллекция Postman"
D=/home/devasc/labs/devnet-src/school-library
install -d "$D"
install -m 0644 "$LAB/src/add100RandomBooks.py" "$D/add100RandomBooks.py"
install -m 0644 "$LAB/src/library.postman_collection.json" /home/devasc/library.postman_collection.json
rm -f "$D/list_all_books.py" "$D/add100MoreBooks.py" /home/devasc/token.json /home/devasc/swagger.json
# readline: список fake.<Tab><Tab> в python3 выводится целиком, без пейджера --More--
printf '%s\n' '$include /etc/inputrc' 'set page-completions off' 'set enable-bracketed-paste off' \
  > /home/devasc/.inputrc
chown -R devasc:devasc /home/devasc/labs
chown devasc:devasc /home/devasc/library.postman_collection.json /home/devasc/.inputrc
echo "OK"
