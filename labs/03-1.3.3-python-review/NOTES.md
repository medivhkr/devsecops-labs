# 1.3.3 Lab - Python Programming Review: заметки к сценарию

## Среда

`env: container`: Ubuntu 20.04 с Python 3.8 из apt, как в ВМ DEVASC (пользователь devasc, хост labvm).
Службы, systemd, сеть и маршрутизатор не нужны, работа идёт в терминале и в интерпретаторе Python.

`prepare.sh` создаёт `~/labs/devnet-src/python/devices.txt` (15 устройств, как в ВМ DEVASC).
Последняя строка не заканчивается переводом строки: только при этом вывод совпадает с Part 7 Step 1c
методички, где после последнего устройства нет пустой строки.

## Соответствие шагов

| Методичка | Шаги сценария (id) |
|---|---|
| Part 1 | env |
| Part 2 Step 1a | python_version |
| Part 2 Step 1b–3c | repl_calc_strings (одна сессия python3, как в методичке) |
| Part 2 Step 4 | hello_world_file, cd_python, cat_hello_world, run_hello_world, cd_home, run_hello_world_path |
| Part 3 Step 1–5 | cd_devnet_src, repl_types, repl_boolean, repl_variable, repl_concat, repl_casting |
| Part 4 Step 1–2 | repl_list, repl_dict |
| Part 5 Step 1 | repl_input |
| Part 5 Step 2 | cd_python_2, personal_info_file, cat_personal_info, run_personal_info |
| Part 6 Step 1–2 | if_vlan_file … run_if_vlan_same, if_acl_file, cat_if_acl, run_if_acl_10/110/200 |
| Part 6 Step 3 | repl_for (одна сессия, как в методичке) |
| Part 6 Step 4–5 | while_v1_file … run_while_v3 |
| Part 7 Step 1–3 | ls_python, file_access_v1_file … run_file_access_v3 |
| Part 7 Step 4 (Challenge) | file_access_input_file … check_devices_list_2 |

## Отличия от методички

1. Part 1 (запуск ВМ в VirtualBox) команд не содержит. Вместо него шаг `env` показывает ОС, имя хоста
   и пользователя стенда.
2. VS Code (GUI) не запускается. Файлы создаются шагом `write_file` (аналог сохранения в редакторе),
   показываются через `cat` и запускаются `python3 <файл>` в терминале. Part 2 Step 4e (Run > Run Without
   Debugging, запуск через debugpy) не воспроизводится, ближайшая замена — запуск из терминала (Step 4f).
3. labrun в конце каждого шага ждёт приглашение bash, поэтому сессия интерпретатора не переходит из
   шага в шаг. В методичке одна сессия идёт от Part 3 Step 1 до Part 5 Step 1, в сценарии для каждого
   шага `python3` запускается заново и закрывается `quit()`. Part 2 Step 1b–3c и Part 6 Step 3a–c идут
   одной сессией, как в методичке.
4. Python 3.8.10 вместо 3.8.2 (текущий пакет Ubuntu 20.04). Словарь в Part 4 Step 2c выводится в порядке
   вставки ключей; порядок, напечатанный в методичке, для Python 3.7+ неверен.
5. Добавлено то, что методичка просит сделать, но не показывает: выражение `2+3*4**2/(7-5)` (Part 2
   Step 2b), операторы `>` и `!=` (Part 3 Step 2), проверка ключа `"R3" in ipAddress` (Part 4 Step 2b).
6. Part 5 Step 1: вместо `User_Name` вводится `Bob`. Part 5 Step 2: запускается `personal-info.py` из
   `~/labs/devnet-src/python` (в примере методички опечатка `person-info.py` и другой каталог); скрипт —
   решение из версии с ответами.
7. Part 7 Step 4 (Challenge): `file-access-input.py` — решение из версии с ответами. Добавлены резервная
   копия `devices.txt.bak` и проверка скриптом `file-access.py`. Так как исходный файл не заканчивается
   переводом строки, первое устройство дописывается в ту же строку
   (`Cisco 3860 Catalyst SwitchCisco 1941 Router`). Причина показана `tail -c 27 devices.txt.bak | od -c`;
   файл восстанавливается из копии, в конец добавляется перевод строки (`echo >> devices.txt`), скрипт
   запускается ещё раз, итоговый список содержит 17 устройств. Второе устройство вводится без лишнего
   пробела в конце (в примере методички он есть по ошибке).

## Первый прогон и что проверять при следующих

Первый прогон в GitHub Actions (`outputs/RUN.md`): 62 шага, без `timeout` и
`interact_timeouts`, все коды возврата 0, Python 3.8.10. После него изменён только заголовок шага
ls_python (вывод не меняется).

- В `steps.json` нет `interact_timeouts` и `timeout` (особенно repl_input, repl_for, run_while_v3).
- check_devices_list содержит `'Cisco 3860 Catalyst SwitchCisco 1941 Router'`, check_devices_list_2 —
  17 отдельных устройств.
- Длинные строки (строка print в personal-info.py, списки устройств) переносятся по ширине терминала
  100 колонок, иногда посреди слова, как в окне терминала такой ширины.
