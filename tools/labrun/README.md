# labrun: запись выполнения лабораторной работы

`labrun.py` выполняет шаги работы из `scenario.yml` в интерактивной оболочке bash пользователя
devasc и записывает в протокол всё, что появляется в терминале.

Каждая работа лежит в `labs/<NN>-<номер>-<тема>/`:

- `scenario.yml` — шаги работы;
- `prepare.sh` — подготовка стенда от root до начала записи (в протокол не попадает);
- `src/` — файлы стенда (симуляторы, данные), если их нельзя создать шагом `write_file`.

## Прогон в GitHub Actions

Общий workflow `.github/workflows/_run-lab.yml`:

1. `env: container` — контейнер `ubuntu:20.04`, как ВМ DEVASC (Python 3.8, Ansible 2.9.6 из apt),
   имя хоста `labvm`, capability NET_ADMIN. `env: vm` — ВМ GitHub Actions `ubuntu-24.04` с systemd
   (для служб sshd, apache2, dnsmasq, сетевых пространств имён), Python 3.12.
2. `lab-env/setup-labvm.sh` ставит базовые пакеты (git curl wget nano less tree jq iproute2
   iputils-ping net-tools dnsutils openssh-client sshpass procps python3 python3-pip python3-venv
   python3-yaml python3-paramiko ansible), создаёт пользователя `devasc` (sudo без пароля)
   и каталог `~/labs/devnet-src`.
3. `bash labs/<работа>/prepare.sh` от root, если файл есть: пакеты, службы, файлы-заготовки,
   как они лежат в ВМ DEVASC.
4. `python3 tools/labrun/labrun.py labs/<работа>/scenario.yml --out out/<работа>` от root. labrun
   открывает интерактивный bash пользователя devasc в псевдотерминале 100x50 (приглашение
   `devasc@labvm:~$`) и выполняет шаги по очереди.
5. Результаты (`transcript.txt`, `steps/NN_id.txt`, `steps.json`, `files/`) выгружаются как артефакт.

## Формат scenario.yml

```yaml
lab: "3.5.7"
title: "Create a Python Unit Test"
shell_init:                 # (необязательно) выполняется до начала записи в оболочке devasc
  - "export PYTHONDONTWRITEBYTECODE=1"
collect:                    # файлы и каталоги, которые сохраняются в артефакт (files/)
  - ~/labs/devnet-src/unittest
steps:
  - id: cd_lab                          # уникальный id латиницей
    title: "Part 2 Step 1: переход в каталог"   # заголовок шага в протоколе
    cmd: "cd ~/labs/devnet-src/unittest"
  - id: create_file
    title: "Part 2 Step 2: файл recursive_json_search.py"
    write_file:                          # файл, который в методичке пишется в редакторе
      path: ~/labs/devnet-src/unittest/recursive_json_search.py
      content: |
        ...
  - id: run_tests
    cmd: "python3 -m unittest test_json_search.py"
    timeout: 120                         # секунды (по умолчанию 900)
  - id: repl
    title: "Интерактивный интерпретатор"
    cmd: "python3"
    interact:                            # диалог с интерактивной программой (регулярные выражения pexpect)
      - expect: ">>> "
        send: "print('Hello')"
      - expect: ">>> "
        send: "exit()"
  - id: ping
    cmd: "ping 8.8.8.8"
    interact:
      - expect: "icmp_seq=4 "
        delay: 0.3
        sendcontrol: "c"                 # Ctrl+C
  - id: service_check
    host: "systemctl is-active nginx"    # служебная команда от root, в протокол не попадает
```

## Устройство сценариев

- Шаги идут в том же порядке, что и в методичке; `title` начинается с номера части и шага.
- Команды записаны так же, как в методичке. Строка команды не длиннее ~95 символов
  (терминал 100 колонок).
- Редакторы (nano, vi, VS Code) не запускаются: содержимое файла задаётся шагом `write_file`,
  а затем, если методичка показывает файл, выполняется `cat`.
- Пейджеры отключены (`SYSTEMD_PAGER=cat` в `shell_init`); где методичка использует `| more`,
  выход из пейджера выполняется через `interact` (`expect: "--More--"`, `send: "q"`, `raw: true`).
- Интерактивные программы (`python3`, `ssh`, `input()` в скриптах) ведутся через `interact` с
  ожиданием конкретного текста запроса.
- Ключи и пароли учётных записей не хранятся в сценарии: они приходят из секретов GitHub Actions
  через переменные окружения, которые использует `prepare.sh`, и в протокол не выводятся.
- То, что нельзя выполнить на стенде (графический интерфейс VirtualBox, Packet Tracer, браузер),
  заменено ближайшим рабочим аналогом; отличия описаны в `NOTES.md` работы.
- Стенд поднимается с нуля в каждом прогоне.
- Маршрутизатор CSR1kv запускается из `prepare.sh` командой `bash "$REPO/lab-env/start-csr1kv.sh"`
  (эмулятор IOS XE на 192.168.56.101:22, учётная запись из методички cisco / cisco123!). У эмулятора
  есть параметры `--hostname` и `--ipv4` для второго экземпляра (см. `tools/csr1kv_emulator`).

## NOTES.md

В `NOTES.md` работы описаны выбранная среда (container или vm) и причина выбора, соответствие
шагов методички шагам сценария и отличия от методички.
