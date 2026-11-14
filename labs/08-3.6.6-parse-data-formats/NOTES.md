# 3.6.6 Parse Different Data Types with Python: заметки к сценарию

## Среда: container

Контейнер ubuntu:20.04 с Python 3.8, как ВМ DEVASC. Службы, сеть и устройства не нужны: работа
использует только Python 3, стандартные модули `xml.etree.ElementTree`, `re`, `json` и PyYAML.
PyYAML берётся из пакета `python3-yaml` (на 20.04 это версия 5.3.1), его ставит
`lab-env/setup-labvm.sh`. Методичка ничего не устанавливает (в ВМ DEVASC PyYAML уже есть),
поэтому `pip3 install` в сценарии нет. `xmltodict` в работе не используется.

## Подготовка (prepare.sh)

В ВМ DEVASC файлы лежат в `~/labs/devnet-src/parsing` заранее. `prepare.sh` копирует их из `src/parsing/`:

- `myfile.xml`, `myfile.json`, `myfile.yaml` побайтно совпадают с текстом методички
  (сверено по itexamanswers.net, версия DEVASC v1, и по `cat` этих файлов в ВМ DEVASC
  в блоге miqbal.staff.telkomuniversity.ac.id/parsing-dengan-python);
- заготовки `parsexml.py`, `parsejson.py`, `parseyaml.py` содержат одну строку-комментарий.
  Текст комментария подтверждён только для `parseyaml.py`, для двух других он написан по аналогии.
  Заготовки в протокол не выводятся (видны только в `ls -l`) и перезаписываются шагами `write_file`.

## Соответствие шагов

| Методичка | Шаги сценария |
|---|---|
| Part 1 (запуск ВМ) | `env`, `pyyaml_version` |
| Part 2 Step 1a | `cd_parsing`, `ls_parsing`, `cat_xml` |
| Part 2 Step 1b–e / Step 2 | `parsexml` / `run_parsexml` |
| Part 3 Step 1a | `cat_json` |
| Part 3 Step 1b–d / 2a | `parsejson_v1` / `run_parsejson_v1` |
| Part 3 Step 2b / 2c | `parsejson_v2` / `run_parsejson_v2` |
| Part 3 Step 3a / 3b | `parsejson_v3` / `run_parsejson_v3` |
| Part 4 Step 1a | `cat_yaml` |
| Part 4 Step 1b–d / 2a | `parseyaml_v1` / `run_parseyaml_v1` |
| Part 4 Step 2b / 2c | `parseyaml_v2` / `run_parseyaml_v2` |
| Part 4 Step 3a / 3b | `parseyaml_v3` / `run_parseyaml_v3` |

## Отличия от методички

1. Part 1 (запуск ВМ DEVASC) не выполняется. Вместо неё показан стенд: ОС, имя хоста,
   версии Python и PyYAML.
2. VS Code заменён шагами `write_file`: на каждую точку «сохранить и запустить» записывается
   накопленная версия скрипта. Промежуточные версии есть в `steps.json`, итоговые в `files/parsing`.
   Код взят из методички без изменений.
3. Добавлены `cd ~/labs/devnet-src/parsing` (в методичке он подразумевается приглашением),
   `ls -l` и `cat myfile.*` (содержимое файлов методичка приводит в тексте).
4. В методичке ожидаемый вывод Part 3 Step 2c напечатан с ошибкой: лишняя строка `1209600`,
   нет двоеточия после «is» и точки после «seconds». В протоколе приведён вывод, который этот код даёт на стенде.

## Проверка протокола

- Все 14 команд завершились с кодом 0. `strict: true` и `expect_exit: 0` делают прогон CI
  красным при любой ошибке.
- `parsexml.py` выводит `merge` и `set`. `yaml.dump` даёт блочный стиль с ключами по алфавиту,
  `json.dumps` даёт отступ в 4 пробела.
- Строка словаря (227 символов) в протоколе перенесена по ширине терминала (100 колонок),
  так она выглядит на экране.
- Пустой строки в конце вывода `parsejson.py` (после YAML) в протоколе не будет: labrun обрезает
  пустые строки в конце шага. В `raw.log` она есть.
- Локальная проверка (Python 3.14, PyYAML 6.0.3) дала для всех семи запусков вывод, совпадающий
  с реальным выводом из методички. На стенде Python 3.8.10 и PyYAML 5.3.1.
