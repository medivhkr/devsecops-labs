# 3.1.12 Lab - Explore Python Development Tools: заметки к сценарию

## Среда

`env: container`: Ubuntu 20.04, `python3`, `python3-venv` и `pip3` из apt, как в ВМ DEVASC
(в методичке Python 3.8.2, в контейнере 3.8.10). Внутри venv работает pip 20.0.2 из Ubuntu
20.04, такой же, как в ВМ DEVASC. pip не обновлялся, потому что методичка этого не делает.
systemd не нужен. На ВМ 24.04 были бы Python 3.12 и PEP 668, это дальше от методички.
Нужен доступ к PyPI.

`prepare.sh` создаёт пустой каталог `~/labs/devnet-src/python`, который в ВМ DEVASC есть заранее.
Он удаляет `devfun`, `devnew`, `requirements.txt` и кэш pip, оставшиеся от прошлого прогона, поэтому
повторный запуск даёт тот же результат.

Запуск в CI: workflow `.github/workflows/lab-3.1.12.yml` (`lab: 04-3.1.12-python-dev-tools`, `env: container`).

## Соответствие шагов (файлы `steps/NN_id.txt`)

| Методичка | Шаг сценария | Команда |
|---|---|---|
| Part 1 (замена) | 01_env | `cat /etc/os-release \| head -4 && whoami && hostname` |
| Part 2 a, b | 02_python_version, 03_which_python | `python3 -V`, `which python3` |
| доп. | 04_pip_version_system | `pip3 --version` |
| Part 3 Step 1a, 1b | 05_cd_python, 06_venv_devfun | `cd labs/devnet-src/python/`, `python3 -m venv devfun` |
| Part 3 Step 2a | 07_activate_devfun | `source devfun/bin/activate` |
| доп. | 08_which_in_devfun | `which python3 pip3` |
| Part 3 Step 2b, 2c, 2d | 09, 10, 11 | `pip3 freeze`, `pip3 install requests`, `pip3 freeze` |
| доп. | 12_list_devfun | `pip3 list` |
| Part 3 Step 2e | 13_deactivate_devfun | `deactivate` |
| Part 3 Step 3a, 3b | 14_system_freeze, 15_system_freeze_requests | `python3 -m pip freeze`, `... \| grep requests` |
| Part 4 a, b | 16, 17 | `source devfun/bin/activate`, `pip3 freeze > requirements.txt` |
| Part 4 c | 18, 19 | `deactivate`, `ls` |
| доп. | 20_cat_requirements | `cat requirements.txt` |
| Part 4 d | 21, 22 | `python3 -m venv devnew`, `source devnew/bin/activate` |
| Part 4 e, f, g | 23, 24, 25 | `pip3 install -r requirements.txt`, `pip3 freeze`, `deactivate` |
| доп. | 26_ls_final | `ls` |

Дополнительные шаги только показывают состояние и ничего не меняют. В артефакт `files/python/`
попадают `requirements.txt` и `pyvenv.cfg` обоих окружений.

## Отличия от методички

1. Part 1: ВМ DEVASC в VirtualBox не запускается. Вместо неё используется контейнер ubuntu:20.04
   с пользователем devasc и именем хоста labvm. Шаг 01 показывает ОС, пользователя и хост.
2. Версии пакетов берутся с PyPI на дату прогона и подходят для Python 3.8. В прогоне установлены
   requests 2.32.4, urllib3 2.2.3, idna 3.15, certifi 2026.10.23 и charset-normalizer 3.5.2 (вместо chardet).
   В методичке есть оговорка, что версии могут отличаться.
3. `pip3 freeze` в новом devfun (шаг 09) ничего не выводит, как и в методичке. `pkg-resources 0.0.0`
   (особенность pip в Ubuntu 20.04) виден только в `pip3 list` (шаг 12) и в `requirements.txt` не попадает,
   хотя в requirements.txt методички эта строка есть.
4. `python3 -m pip freeze` (шаги 14–15) показывает системные пакеты контейнера: ansible 2.9.6 из apt
   с зависимостями, paramiko, pexpect, pyte и т.д. Это не список образа DEVASC.
5. Файлов от лабораторной 1.3.3 в каталоге нет. Поэтому `ls` в Part 4 c (шаг 19) покажет только
   `devfun` и `requirements.txt`. В методичке там уже виден `devnew`, потому что снимок сделан после
   шага d. Итоговый `ls` (шаг 26) показывает все три объекта.

## Проверка протокола

- Шаги 10 и 23 заканчиваются строкой `Successfully installed ...`, в шаге 23 все пакеты берутся из кэша
  (`Using cached`).
- Списки в шагах 11, 20 и 24 совпадают.
- Шаг 15 находит строки с requests (код возврата grep 0).
- В логе CI нет `WARNING` о таймаутах.
