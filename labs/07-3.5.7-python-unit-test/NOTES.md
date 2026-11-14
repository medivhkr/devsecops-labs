# 3.5.7 Create a Python Unit Test: заметки к сценарию

## Среда

`env: container` (ubuntu:20.04). В ВМ DEVASC тоже Ubuntu 20.04 и Python 3.8, поэтому вывод
unittest совпадает с методичкой по форме: в скобках после имени теста только модуль и класс
(`__main__.json_search_test`), относительный путь `File "test_json_search.py"` при запуске
скрипта, `optional arguments:` в справке. Службы systemd не нужны. Пакеты не ставятся:
unittest входит в стандартную библиотеку, pytest в работе не используется.

`prepare.sh` создаёт `~/labs/devnet-src/unittest`, как в ВМ DEVASC: `test_data.py` (из `src/`)
и две заготовки `recursive_json_search.py` и `test_json_search.py` со строкой
`# Fill the Python code in this file`.

## Шаги методички и шаги сценария

| Методичка | Шаги сценария (id) |
|---|---|
| Part 1 | `env` (ОС, имя хоста, версия Python) |
| Part 2, вопросы 1-2 | `cd_devnet_src`, `q1_q2_repl` |
| Part 2, вопрос 3 | `unittest_help` (`python3 -m unittest -h`) |
| Part 3, Step 1 | `ls_unittest`, `more_test_data` |
| Step 2a-2d | `cd_unittest`, `rjs_v1`, `cat_rjs_v1`, `run_rjs_v1` (`[]`), `grep_issue_summary` |
| Step 3 | `test_file`, `cat_test_file` |
| Step 4a-4b | `run_test_script` (`.F.`), `run_unittest_verbose` |
| Step 5a-5b | `rjs_v2`, `cat_rjs_v2`, `run_rjs_v2` |
| Step 6a-6b | `run_unittest_2` (`..F`), `grep_keys` |
| Step 7a-7c | `repl_global_ret_val`, `rjs_v3`, `cat_rjs_v3`, `run_discover` (`...`, `OK`), `run_discover_verbose` |

## Отличия от методички

- Part 1: вместо ВМ в VirtualBox используется контейнер с тем же пользователем, именем хоста и каталогом.
- Part 2: в методичке ответы на вопросы 1-2 ищут в документации на python.org. Здесь они дополнительно
  проверены в интерпретаторе: `TestCase.__doc__` и `TestLoader.testMethodPrefix`. Вывод `-h` приведён
  полностью (в методичке часть вывода пропущена). Ширина терминала 100 колонок, поэтому argparse
  переносит строки справки не так, как в окне на 80 колонок.
- Код вводится шагом `write_file` (в методичке его вставляют в VS Code), после каждой версии файла
  выполняется `cat -n`. Подшаги 3b-3e объединены в один `write_file`. В Step 7b содержимое файла заменено
  целиком, поэтому строки-заготовки в нём нет и в файле 29 строк.
- Операторы кода совпадают с методичкой, а комментарии и docstring написаны своими словами, число строк
  сохранено. Поэтому строки под `FAIL:` и под именами тестов в
  режиме `-v` отличаются от PDF по словам, смысл тот же. Номера строк в трассировках (11 и 14) те же.
- `test_data.py` восстановлен по сторонней копии файла из ВМ DEVASC. Длинное значение `errorDescription`
  в ней сокращено. На тесты это не влияет.
- Step 1: терминал высотой 50 строк, поэтому первый экран `more` больше, чем в методичке. Приглашение
  `--More--(NN%)` при выходе по `q` стирается и в протоколе не видно (видно в `raw.log`).
- Steps 2d и 6b: поиск по `test_data.py` в редакторе заменён на `grep -n`.
- Step 7a (дополнительно): в интерпретаторе показано, что глобальный `ret_val` растёт от вызова к вызову
  (1, 2, 3 записи), а поиск `key2` возвращает те же три записи. Порядок вызовов повторяет порядок тестов.
- Step 7c (дополнительно): `python3 -m unittest -v` после исправления. Необязательное удаление `print()`
  не выполнялось.
- `PYTHONDONTWRITEBYTECODE=1`: `__pycache__` не создаётся, устаревший байткод после быстрой перезаписи
  файла исключён.

## Проверка протокола

- Коды возврата в `steps.json`: `run_test_script`, `run_unittest_verbose` и `run_unittest_2` дают 1,
  `run_rjs_*`, `run_discover*` и `unittest_help` дают 0. Предупреждений `unexpected_exit` и
  `interact_timeouts` быть не должно.
- Строки прогресса `.F.`, `..F`, `...`; в трассировках строки 11 и 14; `Python 3.8.x` в шаге `env`.
- Строка трассировки `test_search_not_found` с абсолютным путём занимает 101 символ и в терминале на 100
  колонок переносится (последняя буква на следующей строке). Это не ошибка.
- `more_test_data`: показан первый экран `test_data.py`, шаг завершился по `q` без таймаута.
- REPL-шаги (`q1_q2_repl`, `repl_global_ret_val`) завершились через `exit()`.
