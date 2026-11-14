#!/usr/bin/env bash
# Запуск эмулятора CSR1kv на адресе 192.168.56.101 (как в методичках DEVASC).
# Требуется root и capability NET_ADMIN (для добавления адреса на lo).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
ADDR="${CSR_ADDR:-192.168.56.101}"

ip addr add "${ADDR}/32" dev lo 2>/dev/null || true
nohup python3 "$REPO/tools/csr1kv_emulator/csr1kv_emulator.py" \
  --host "$ADDR" --port 22 --host-key /root/csr1kv_host_key --log /tmp/csr1kv.log >/tmp/csr1kv.out 2>&1 &

for i in $(seq 1 30); do
  if (exec 3<>"/dev/tcp/${ADDR}/22") 2>/dev/null; then
    echo "CSR1kv emulator is listening on ${ADDR}:22"
    exit 0
  fi
  sleep 1
done
echo "emulator did not start" >&2
cat /tmp/csr1kv.out >&2
exit 1
