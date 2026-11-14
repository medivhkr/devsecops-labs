# 4.9.2 Integrate a REST API in a Python Application (вариант OSM без ключа): заметки

## Зачем этот вариант

Ключа MapQuest нет, а без него `scenario.yml` доходит до конца только с ошибками API.
`scenario-osm.yml` выполняет ту же лабораторную на открытых сервисах OpenStreetMap, без ключей и секретов:

- место -> координаты: Nominatim, `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=<место>`;
- маршрут: демо-сервер OSRM,
  `https://router.project-osrm.org/route/v1/driving/<lon1>,<lat1>;<lon2>,<lat2>?overview=false&steps=true&radiuses=50000;50000`.

Среда `container`, как в основном варианте. `prepare.sh` общий: он ставит requests, curl, jq и создаёт
`~/labs/devnet-src/mapquest`. Без секрета `MAPQUEST_KEY` он только пишет в лог CI предупреждение,
это ожидаемо. Каталог лабораторной тот же, файлы называются `osm_parse-json_1.py` … `osm_parse-json_7.py`.

Запуск: workflow `.github/workflows/lab-4.9.2-osm.yml`, вручную или при изменении `scenario-osm.yml`, без расписания, чтобы не нагружать публичные серверы:

```yaml
jobs:
  lab:
    uses: ./.github/workflows/_run-lab.yml
    with:
      lab: 10-4.9.2-rest-api-python
      env: container
      scenario: scenario-osm.yml
      artifact: 10-4.9.2-rest-api-python-osm
```

## Соответствие методичке

| Методичка | Шаги сценария / скрипт |
|---|---|
| Part 1 | `env_os_python`, `env_requests` |
| Part 2 | не выполняется: демонстрация преподавателем, тот же диалог есть в Part 6 |
| Part 3 (ключ) | замена: ключ не нужен; `ua_var` задаёт User-Agent; `nominatim_status` и `osrm_nearest` показывают, что сервисы отвечают без ключа |
| Part 4 Step 2–4 | `_1`: импорт; затем геокодирование двух мест, URL через `urlencode`, вывод URL и HTTP-кодов, ответ OSRM словарём (`print(json_data)`) |
| Part 4 Step 5–6 | `_2`: `print(json_data)` удалён, проверка `json_data["code"] == "Ok"` |
| Part 4 Step 7–10 | `_3`: цикл с `input()`, остановка Ctrl+C; `_4`: выход по `quit`/`q`, четыре запуска |
| Part 4 Step 11, Part 5 Step 3, 6b | вместо Chromium + JSONView: `curl` сохраняет тот же URL в `/tmp`, структура показывается `jq` |
| Part 5 Step 1–2 | `_5`, три редакции: время ЧЧ:ММ:СС и мили; добавлены километры без округления; округление `format()` |
| Part 5 Step 4–5 | `_6`: функция `narrative()` и цикл `for` по шагам, километры на каждом шаге |
| Part 5 Step 6a | `_6` с Beijing, China и Bal печатает только URL: ответ `NoSegment` в `_6` не обрабатывается |
| Part 5 Step 6c–d | `_7`: пустой ввод, неизвестное место, `NoSegment`, `NoRoute`, прочие коды, сетевые и HTTP-ошибки |
| Part 6 | `_7` на вводах методички и одной дополнительной паре (`Xyzzy Qwerty 0000`) |

## Чем отличается от MapQuest

- Вместо одного запроса к MapQuest делается три: два к Nominatim (по одному на место) и один к OSRM.
  OSRM принимает координаты в порядке «долгота,широта».
- Поля JSON:

  | MapQuest | OSRM |
  |---|---|
  | `info.statuscode` = 0 | `code` = "Ok" |
  | `route.formattedTime` | `routes[0].duration` в секундах, ЧЧ:ММ:СС считает скрипт |
  | `route.distance` в милях | `routes[0].distance` в метрах: км = м / 1000, мили = км / 1.61 |
  | `route.fuelUsed` | нет, выводится `Fuel Used: not provided by OSRM` |
  | `legs[0].maneuvers[].narrative` и `distance` (мили) | `legs[0].steps[]`: текст строит `narrative()` из `maneuver.type`, `maneuver.modifier`, `name`, `ref`, `destinations`; `distance` в метрах |

- Ошибки: вместо 402 скрипт выводит `NoSegment`/`NoRoute` от OSRM или «Unknown location», если Nominatim
  вернул `[]`. Вместо 611 скрипт сам проверяет пустой ввод и запрос не отправляет. Для прочих кодов
  выводится ссылка на документацию OSRM.
- **В URL маршрута добавлен параметр `radiuses=50000;50000`.** Без него демо-сервер привязывает Вашингтон
  к дороге в Португалии (5865 км от точки) и отвечает `Ok`: маршрут Washington → Beijing получается
  11 814 км, Washington → Bal 8604 км. С `radiuses` OSRM отвечает `NoSegment` (HTTP 400, тело в JSON).
  Шаги `curl_snap_json` и `jq_snap` показывают это в протоколе.
- Ключа нет, поэтому DevSecOps-шаги про ключ (`key_*`, `rm_saved_json`, `key_leak_check`) убраны. Вместо них
  `grep_policy` проверяет User-Agent и паузу во всех версиях.
- Версия 1 печатает URL и HTTP-код каждого запроса (дополнительно к методичке) и словарь ответа (как в методичке).
  Начиная с версии 2 остаются только URL и состояние API. Из-за констант и функции `geocode()` трейсбек
  после Ctrl+C указывает на строку 24, а не 9.
- "Bal" Nominatim находит: это провинция Балх в Афганистане. Поэтому ответ `NoSegment`, а не 402. Для ветки
  «неизвестное место» в Part 6 добавлена пара Washington, D.C. → `Xyzzy Qwerty 0000`.
- Числа другие, чем в методичке: Washington → Baltimore 01:01:02, 62.67 км, 20 шагов; Moscow → Beijing
  88:23:11, 7204.13 км, 186 шагов (живой прогон 14.11.2026).

## Правила публичных серверов

- Nominatim (https://operations.osmfoundation.org/policies/nominatim/):
  - не больше 1 запроса в секунду;
  - User-Agent должен называть приложение: со стандартным User-Agent python-requests сервер отвечает 403, это проверено;
  - результаты нужно кэшировать, повторы одного запроса нежелательны;
  - массовое геокодирование и автодополнение запрещены;
  - за нарушения сервер блокирует.

  Скрипты передают User-Agent, ждут 1 с перед каждым запросом и задают `timeout=20`.
- OSRM (https://github.com/Project-OSRM/osrm-backend/wiki/Demo-server): не больше 1 запроса в секунду,
  только разумное некоммерческое использование, гарантий доступности нет.
- Данные © участники OpenStreetMap (ODbL), в отчёте с маршрутами нужна эта атрибуция.
- За прогон: 30 поисков в Nominatim (плюс один запрос status) и 18 запросов к OSRM. Кэша в скриптах нет,
  чтобы сохранить простоту лабораторной. По расписанию и в цикле сценарий не запускать.

## Риски

- У сервисов нет SLA. Возможны недоступность, HTTP 429/403 и блокировка IP-адресов GitHub Actions. Версии 1–6
  тогда падают с трейсбеком, а ожидания `interact` заканчиваются по таймауту. Версия 7 выводит «Request failed».
- Данные OSM меняются: время, расстояния, тексты шагов и место для «Bal» могут стать другими. Координаты в
  шагах `curl` (от Nominatim на 14.11.2026) могут перестать совпадать с URL, который печатает скрипт.
- Большой вывод: словарь в версии 1 занимает около 38 КБ, маршрут Moscow → Beijing около 190 строк.
  Названия улиц на кириллице и китайском выводятся в UTF-8.
- Логика привязки точек на демо-сервере может измениться: Beijing и Bal могут дать `NoRoute` вместо
  `NoSegment`. Версия 7 обрабатывает оба кода.

## Что проверить в результатах прогона

- Нет предупреждений `interact_timeouts`. `nominatim_status` возвращает `"status":0`, а в `run_v1` все три
  HTTP-кода 200.
- `jq_error_body` показывает `NoSegment`, `jq_snap` показывает `Ok` и `distance` около 5.8e6 м.
- В `run_v7_all` есть все ветви: два маршрута, два `NoSegment`, Unknown location, Missing an entry, quit.
