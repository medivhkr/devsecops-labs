# 1.2.2 Lab - Linux Review: заметки к сценарию

## Среда: `vm` (ВМ раннера Ubuntu 24.04 с systemd)

Почему не `container` (Ubuntu 20.04, ближе к DEVASC):

- Part 5 Step 1c требует запланировать и отменить выключение (`shutdown +1 "Come back soon!"`,
  `shutdown -c`). Это делает systemd-logind, а в контейнере без systemd команда не работает.
- Part 5 Step 3 (`ps -e`, `ps -ef`, `ps -e | more`): в контейнере видно 5–10 процессов, без systemd
  и потоков ядра. `| more` не дошёл бы до приглашения `--More--`.

Недостаток такого выбора: на стенде Ubuntu 24.04, а не 20.04. Поэтому:

- в выводе apt репозитории noble;
- speedtest-cli версии 2.1.3, а не 2.1.2;
- дата в `passwd -S` в формате ISO (`2026-11-14`);
- в `ip address` и `/etc/passwd` есть интерфейсы и пользователи раннера.

Запуск в CI: workflow `.github/workflows/lab-1.2.2.yml` (`lab: 02-1.2.2-linux-review`, `env: vm`).

## Что воссоздаёт prepare.sh (как в ВМ DEVASC «из коробки»)

- **Домашний каталог:** папки `Desktop Documents Downloads Music Pictures Public Templates Videos snap`.
  На рабочем столе 7 ярлыков `.desktop` с именами из методички, включая опечатку `pacet`. Содержимое
  ярлыков (`src/Desktop/`) составлено заново, с ВМ не копировалось, поэтому размеры в `ls -l` другие.
- **Учётная запись devasc:** полное имя `DEVASC` (поле GECOS `DEVASC,,,`) нужно для Part 4a, пароль
  `Cisco123!`. UID назначает useradd в setup-labvm.sh, и он не равен 900, как в ВМ DEVASC, поэтому
  строки в `grep '[8-9]'` отличаются.
- **Окружение оболочки** (через `shell_init`): локаль en_US.UTF-8 (от неё зависят порядок `ls` и формат
  `date`) и umask 002 (от него зависят права `-rw-rw-r--` в Part 3).
- **Сеть:** dummy0 с адресами 192.0.2.1–5/32.
- **Справка:** man-db и страницы `man ls` и `man passwd`.
- **apt:** убран `Assume-Yes` раннера GitHub, чтобы появлялись настоящие запросы `[Y/n]`. Включены debconf
  Noninteractive и `--force-confold`. needrestart только выводит список служб и ничего не перезапускает.

## Соответствие шагам методички

| Методичка | id шагов |
|---|---|
| Part 1, Part 2 Step 1 | `env` (вывод `head -n 4 /etc/os-release && hostname && whoami`; в методичке команды нет) |
| Part 2 Step 2a–l | `ls` … `pwd_home` (по шагу на команду) |
| Part 2 Step 3a | `apt_update` |
| Part 3 Steps 1–5 | `ls_desktop` … `ls_removed` |
| Part 3 Step 6 | `cd_home` (добавлен), затем `echo_linux` … `cat_linux` |
| Part 3 Step 7 | `vi_linux3` (write_file), `cat_linux3` |
| Part 4 a–h | `grep_devasc` … `grep_star` |
| Part 5 Step 1b–c | `date`, `shutdown_schedule`, `shutdown_cancel` и служебный host-шаг `shutdown_guard` |
| Part 5 Step 2 | `ip_address`, `ping_lan`, `ping_cisco` |
| Part 5 Step 3 | `ps`, `ps_e`, `ps_e_more`, `ps_ef` |
| Part 5 Step 4 | `apt_update2`, `apt_search`, `apt_install`, `speedtest`, `apt_upgrade`, `apt_purge` |
| Part 5 Step 5 | `passwd`, `passwd_status`, `man_passwd`, `man_passwd_status` (добавлен) |

## Отличия от методички

1. **ВМ и терминал не запускаются (Part 1, Part 2 Step 1).** Вместо этого шаг `env` показывает стенд.
2. **`man ls` и `man passwd` открываются через `more`, а не через `less`** (`MANPAGER=more`). less рисует
   страницу, позиционируя курсор, и в протоколе (это эмулятор экрана) получилась бы каша. Клавиши
   те же: пробел листает страницу, q выходит. Для Step 5c добавлен
   `man passwd | grep -B 1 -A 6 'Display account status'`, который выводит описание ключа `-S`.
3. **Part 3 Step 6: добавлен `cd ~`.** Step 5 заканчивается в `~/Documents`, а в методичке приглашение
   уже `~`.
4. **Part 3 Step 7: vi не запускается.** Файл `linux3.txt` с текстом из методички создаёт шаг
   write_file, затем выполняется `cat`. Файл `linux2.txt` не меняется, как и в vi после `:w linux3.txt`.
5. **Part 5 Step 1a: `shutdown now` не выполняется.** Методичка разрешает этот шаг пропустить, а
   раннер бы выключился.
6. **Part 5 Step 1c выполняется через `sudo shutdown ...`.** Оболочка записи не является локальным
   графическим сеансом, и без sudo polkit потребует аутентификацию. Сразу после этого шага host-шаг
   `shutdown_guard` ещё раз отменяет выключение.
7. **Part 5 Step 2b: адрес 192.168.1.1 — это сетевое пространство имён `lan-router`.** Оно подключено
   к ВМ через veth `lan0` с адресом 192.168.1.10/24 и заменяет домашний маршрутизатор, которого в CI
   нет. Поэтому `lan0` виден в `ip address`, а у ответов ttl=64.
8. **Часть вывода зависит от сети раннера и фиксируется как есть:**
   - `ping www.cisco.com`: ICMP в интернет из сети раннера может блокироваться, тогда будет 100% потерь;
   - `speedtest-cli` может завершиться ошибкой;
   - `apt-get upgrade` обновляет то, что вышло после сборки образа раннера.
9. **Part 5 Step 5a: пароль меняется с `Cisco123!` на `Tq7#vLm2Rx`.** Это учебные пароли одноразового
   раннера. В протоколе пароли не видны, потому что passwd отключает эхо.

## Проверка протокола

- **`steps.json`:**
  - нет `timeout`;
  - `interact_timeouts` допустимы только у необязательных запросов `[Y/n]`: если запроса не было,
    шаг просто ждёт 45–90 с;
  - у `run_denied` код 126.
- **`shutdown_schedule`:** есть строка «Shutdown scheduled for …», а host-шаг `shutdown_guard`
  завершился с кодом 0.
- **`man_ls`, `ps_e_more`, `man_passwd`:** появлялось `--More--`, вывод читается без мусора.
- **`ls`:** порядок en_US (`Desktop Documents Downloads labs Music …`), `ls -l myfile.sh` показывает
  `-rw-rw-r--`.
- **`ping_lan`:** получены 4 ответа.
- **`passwd`:** «password updated successfully».
- **`apt_upgrade`:** в прогоне обновлено 14 пакетов за 84 с, кроме запроса `[Y/n]` диалогов не было.

- Part 5 Step 3c: выход из `more` выполнен клавишей q, а не Ctrl+C: в прогоне CI `more` из util-linux 2.39 не завершался по Ctrl+C на приглашении --More--.
