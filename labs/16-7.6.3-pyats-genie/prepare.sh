#!/usr/bin/env bash
# Подготовка стенда для лабораторной 7.6.3 (root, в протокол не попадает).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
bash "$REPO/lab-env/start-csr1kv.sh"
mkdir -p /home/devasc/labs/devnet-src
chown -R devasc:devasc /home/devasc/labs
