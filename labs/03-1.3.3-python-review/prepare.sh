#!/usr/bin/env bash
# Подготовка стенда для лабораторной 1.3.3 (выполняется от root, в протокол не попадает).
# В ВМ DEVASC в каталоге ~/labs/devnet-src/python уже лежит devices.txt со списком 15 устройств.
# Последняя строка файла не заканчивается переводом строки: только так получается вывод
# методички в Part 7 Step 1c, где после последнего устройства нет пустой строки.
set -euo pipefail

D=/home/devasc/labs/devnet-src/python
mkdir -p "$D"

# Файлы, которые создаются по ходу работы, удаляются: повторная подготовка даёт то же исходное состояние
rm -f "$D/hello-world.py" "$D/personal-info.py" "$D/if-vlan.py" "$D/if-acl.py" "$D/while-loop.py" \
  "$D/file-access.py" "$D/file-access-input.py" "$D/devices.txt.bak"

printf '%s\n' \
  "Cisco 819 Router" \
  "Cisco 881 Router" \
  "Cisco 888 Router" \
  "Cisco 1100 Router" \
  "Cisco 4321 Router" \
  "Cisco 4331 Router" \
  "Cisco 4351 Router" \
  "Cisco 2960 Catalyst Switch" \
  "Cisco 3850 Catalyst Switch" \
  "Cisco 7700 Nexus Switch" \
  "Cisco Meraki MS220-8 Cloud Managed Switch" \
  "Cisco Meraki MX64W Security Appliance" \
  "Cisco Meraki MX84 Security Appliance" \
  "Cisco Meraki MC74 VoIP Phone" > "$D/devices.txt"
printf '%s' "Cisco 3860 Catalyst Switch" >> "$D/devices.txt"

chown -R devasc:devasc /home/devasc/labs
echo "devices.txt: $(wc -c < "$D/devices.txt") bytes, last byte: $(tail -c 1 "$D/devices.txt" | od -An -c)"
