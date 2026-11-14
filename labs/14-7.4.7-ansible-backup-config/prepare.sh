#!/usr/bin/env bash
# Подготовка стенда для лабораторной 7.4.7 (выполняется от root, в протокол не попадает).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"

bash "$REPO/lab-env/start-csr1kv.sh"

# Исходное состояние каталога ~/labs/devnet-src/ansible, как в ВМ DEVASC:
# пустой inventory и ansible.cfg с одним комментарием.
D=/home/devasc/labs/devnet-src/ansible
mkdir -p "$D/ansible-csr1000v" "$D/ansible-apache"
: > "$D/ansible-csr1000v/hosts"
echo "# Add to this file for the Ansible lab" > "$D/ansible-csr1000v/ansible.cfg"
: > "$D/ansible-apache/hosts"
echo "# Add to this file for the Ansible lab" > "$D/ansible-apache/ansible.cfg"
chown -R devasc:devasc /home/devasc/labs
