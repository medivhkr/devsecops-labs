#!/usr/bin/env bash
# Подготовка стенда для лабораторной 7.0.3 (root, в протокол не попадает).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
bash "$REPO/lab-env/start-csr1kv.sh"
