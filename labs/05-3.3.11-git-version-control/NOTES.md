# 3.3.11 Software Version Control with Git: заметки к сценарию

## Среда

`env: container`: контейнер ubuntu:20.04, как ВМ DEVASC (bash 5.0, Git 2.25.1, пользователь devasc,
имя хоста labvm). Службы и systemd не нужны: работа идёт в терминале, с GitHub связь по SSH.
Запуск в CI: workflow `.github/workflows/lab-3.3.11.yml` (`lab: 05-3.3.11-git-version-control`, `env: container`),
только вручную (`workflow_dispatch`). Секрет `DEVASC_STUDY_TEAM_KEY` передаёт в `prepare.sh` общий `_run-lab.yml`.

## Соответствие методичке

Шаги идут в порядке методички, `title` каждого шага начинается с «Part N Step M». Part 1 (запуск ВМ)
заменён контейнером CI. Part 2 Step 1: терминал открывает labrun, в нём выводятся ОС, имя хоста и
версия Git. Part 7 Steps 1–3 (учётная запись, вход, создание репозитория) выполнены заранее
в веб-интерфейсе GitHub: репозиторий `medivhkr/devasc-study-team` существует и пуст. В протокол
эти шаги не входят.

## Отличия от методички

1. Идентичность Git: `user.name "Adis Azamatov"` и `user.email 147084862+medivhkr@users.noreply.github.com`
   (noreply-адрес GitHub) вместо `SampleUser` / `sample@example.com`. Методичка разрешает сразу указать
   данные GitHub. В Part 7 Step 7c те же команды выполняются ещё раз, значения не меняются.
   С noreply-адресом push не отклоняется ошибкой GH007.
2. `ls` в домашнем каталоге показывает только `labs`: в контейнере нет рабочего стола.
   `git config --list` дополнительно показывает `init.defaultbranch=master` (его задаёт
   `lab-env/setup-labvm.sh`; Git 2.25 этот параметр не читает, ветка по умолчанию и так master).
3. В `shell_init` задано `GIT_PAGER=cat`: `git log`, `git diff`, `git branch` выводят всё сразу,
   нажимать `q` не нужно. `GIT_EDITOR=true` только страхует: все фиксации идут с `-m`.
4. Part 4 Step 5b: `git diff HEAD~1 HEAD` вместо `git diff <ID первой> <ID второй>`, потому что
   идентификаторы фиксаций до прогона неизвестны. HEAD~1 здесь первая фиксация, HEAD вторая.
5. Part 6 Step 13: вместо `vim` (dd на четырёх строках, `:wq`) файл записывается шагом `write_file`
   с тем же результатом: строка DevNet и две общие строки. Затем `git add` и `git commit -a -m` (Step 15).
6. Part 7: вместо `https://github.com/...` и пароля используется SSH-адрес
   `git@github.com:medivhkr/devasc-study-team.git`. Пароль учётной записи для Git по HTTPS GitHub
   не принимает с 13.08.2021. Ключ развёртывания (deploy key) с правом записи приходит из секрета
   `DEVASC_STUDY_TEAM_KEY`: `prepare.sh` пишет его в `/home/devasc/.ssh/id_ed25519` (600) и добавляет
   ключи github.com через `ssh-keyscan`. Ключ в протокол и журнал CI не выводится.
7. Part 7 Step 8b: `git remote --verbose`, как в методичке (то же, что `git remote -v`).
8. Part 7 Step 11: добавлена проверка `ssh -T git@github.com` (код возврата 1 — норма, GitHub не даёт
   оболочку). `git push -u origin master` вместо `git push origin master`: `-u` связывает master
   с origin/master. Запросов имени и пароля нет.
9. Part 7 Step 12: вместо просмотра в браузере выполняются `git ls-remote origin`, `git clone`
   в `/tmp`, `ls` и `cat`.
10. Ожидаемые ненулевые коды возврата: `git merge test` (1, конфликт), `git log` в пустом
    репозитории (128), `ssh -T` (1). Хэши, даты и права файлов (umask 022) отличаются от примеров.

## Проверка протокола и повторный прогон

- Журнал шага «Подготовка стенда»: `Ключ установлен: 256 SHA256:... (ED25519)` и
  `OK: репозиторий доступен по ключу и пуст`. Без ключа шаги ssh/push/ls-remote/clone
  завершатся с `Permission denied (publickey)`.
- Шаг `push`: строка `* [new branch]      master -> master`; шаг `cat_clone`: три строки файла.
- Повторный прогон: в репозитории уже будет master от прошлого прогона, и push будет отклонён
  (другая история). Перед повтором репозиторий нужно пересоздать пустым и снова добавить
  в него deploy key, потому что ключ привязан к репозиторию.
