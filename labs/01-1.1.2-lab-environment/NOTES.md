# 1.1.2 Install the Virtual Machine Lab Environment: заметки к сценарию

Среда: `container` (ubuntu:20.04, имя хоста `labvm`, пользователь `devasc`). ВМ DEVASC построена на
Ubuntu 20.04 с Python 3.8 и Ansible 2.9.6 из apt, контейнер совпадает с ней по ОС и инструментам.
Службы systemd в этой работе не нужны.

Работа почти целиком графическая: установка VirtualBox, импорт `DEVASC_VM.ova`, рабочий стол MATE,
Packet Tracer, регистрация в DevNet, GitHub и Webex через браузер, Webex Teams. В CI это не выполняется
и не имитируется. Замена: лабораторную ВМ собирает сценарий `lab-env/setup-labvm.sh` (вместо импорта OVA),
а запись проверяет, что эта среда соответствует ВМ DEVASC и что учётная запись GitHub студента существует.

## Соответствие методичке

| Методичка | Шаги сценария | Что сделано |
|---|---|---|
| Part 1 Step 1: установка VirtualBox | `host_platform`, `host_resources` | VirtualBox не ставился. Показано, на чём работает стенд (ядро хоста, контейнер Docker), и ресурсы хоста рядом с требованиями методички (4 ГБ RAM, 15 ГБ диска) |
| Part 1 Step 2: импорт DEVASC_VM.ova | `setup_script` | Образ не импортировался. Показан сценарий сборки среды `lab-env/setup-labvm.sh` (его копия в `~/lab-env/`) |
| Part 2 a: запуск ВМ | `os_release`, `user_host` | Версия ОС, пользователь `devasc`, имя хоста `labvm` |
| Part 2 b, c: EULA Packet Tracer, всплывающие окна | нет | Не выполнялось: нет GUI и Packet Tracer |
| Part 2 d: терминал, VS Code, Packet Tracer, Chromium, Postman | `tool_versions`, `venv_*` | Только терминал: версии python3, pip3, git, ansible; создание, активация и выход из venv |
| Part 2 e: меню Places, System, All applications | `home_layout` | Только домашний каталог и `~/labs/devnet-src` в терминале |
| Part 3 Step 1: учётная запись DevNet | нет | Не выполнялось: регистрация в браузере, без входа в CI не проверить |
| Part 3 Step 2: учётная запись GitHub | `github_site`, `github_api`, `github_profile` | Регистрация идёт в браузере, в CI она не выполнялась. Проверено, что github.com доступен и учётная запись `medivhkr` существует (API и страница профиля) |
| Part 3 Step 3: учётная запись Webex | нет | Не выполнялось |
| Part 3 Step 4: выключение ВМ | `sudo_list`, `sudo_whoami` | `sudo shutdown -h now` и `sudo reboot` не выполнялись: PID 1 в контейнере не systemd, выключение стенда соответствует концу задания CI, после которого контейнер удаляется. Проверены права sudo, нужные этим командам |
| Part 4: Webex Teams | нет | Не выполнялось: GUI-приложение и учётная запись Webex |

В Части 2 методички нет нумерованных шагов, только пункты a–e, поэтому заголовки имеют вид `Part 2 Step a`.

## prepare.sh

- копирует `lab-env/setup-labvm.sh` в `/home/devasc/lab-env/` для шага `setup_script` (в настоящей ВМ DEVASC
  этого каталога нет, он виден в выводе `tree ~`);
- создаёт `~/labs/devnet-src`, если его нет;
- добавляет `labvm` в `/etc/hosts`, если Docker этого не сделал;
- пишет `Set disable_coredump false` в `/etc/sudo.conf`: sudo 1.8.31 в контейнере без CAP_SYS_RESOURCE
  печатает `setrlimit(RLIMIT_CORE): Operation not permitted`. Права sudo от этого не меняются.

## Проверка протокола

- `host_platform`: файл `/.dockerenv` есть, шаг завершается с кодом 0.
- `sudo_list`, `sudo_whoami`: нет предупреждений sudo и запроса пароля.
- `github_api`: выведены строки `"login"` и `"html_url"`. Без токена API GitHub принимает 60 запросов
  в час с одного IP, при превышении лимита прогон повторяется; `github_profile` показывает `HTTP/2 200`.
- `host_resources`: показаны фактические RAM и диск раннера (в прогоне 15 ГБ RAM и 145 ГБ диска, свободно 85 ГБ), это больше требований методички.
