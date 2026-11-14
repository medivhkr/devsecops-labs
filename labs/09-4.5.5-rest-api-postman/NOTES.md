# 4.5.5 Explore REST APIs with API Simulator and Postman: заметки к прогону

## Среда

`env: container` (ubuntu:20.04, Python 3.8, как ВМ DEVASC). Службы systemd не нужны: симулятор API
запускается из `prepare.sh` фоновым процессом от root.

## Что на стенде не так, как в ВМ DEVASC

- **Симулятор School Library API переписан.** Оригинальное приложение Cisco (`/opt/API-SIMULATOR`,
  Flask + flask-restplus) не опубликовано. В `src/school_library_sim.py` лежит собственная реализация
  на стандартной библиотеке Python. Она повторяет поведение оригинала по описанию методички и заметкам
  об исходнике: те же URL, четыре начальные книги, вход `loginViaBasic` (cisco / Cisco123!) и
  `loginViaJSON`, токен `cisco|...` в заголовке `X-API-KEY`, параметры `includeISBN`, `sortBy`,
  `author`, `page` (10 книг на страницу, нумерация с 0, заголовок `Link`), коды 200/400/401/404/405/429,
  JSON с отступом 4 пробела, XML/YAML по заголовку Accept, ограничение 6 запросов GET /books за 10 с.
  Описание OpenAPI (Swagger 2.0) отдаётся по `/api/v1/swagger.json`, страница Swagger UI по `/api/v1/docs`.
  В заголовке `Server` ответов стоит `SchoolLibrarySim/1.0`, а не Werkzeug.
- Симулятор слушает `127.0.0.1:80`. В `/etc/hosts` добавлено `127.0.0.1 library.demo.local`
  (в ВМ DEVASC адрес 192.0.2.1).
- **Chromium нет (нет GUI).** Сайт и страница документации запрашиваются `curl`. Список API, замки,
  параметры GET /books и схема авторизации X-API-KEY показаны через `jq` по `swagger.json`, то есть
  по тем же данным, которые рисует Swagger UI. «Try it out / Execute» заменён тем же HTTP-запросом
  через `curl`. Окно «Sign in» заменено запросом пароля `curl -u cisco`; токен сохраняется в `token.json`
  и подставляется в заголовок X-API-KEY (аналог кнопки Authorize).
- **Postman заменён Newman** (официальный CLI-запуск коллекций Postman, Node.js 20 из NodeSource,
  `newman@6`). Коллекция `src/library.postman_collection.json` (формат v2.1) содержит запросы вкладок
  Postman из методички: GET /books; POST /loginViaBasic с Basic Auth; POST /books с API Key
  (Key `X-API-KEY`, Add to Header) и телом raw JSON; GET /books с Query Params `includeISBN=true`,
  `sortBy=author`. Каждый «Send» — отдельный запуск `newman run ... --folder <запрос> --verbose`
  (`--verbose` печатает статус и тело ответа).
- В Postman токен копируется вручную из ответа шага 3 в поле Value шага 4. В Newman это делает
  скрипт Tests запроса POST /loginViaBasic (`pm.collectionVariables.set("token", ...)`), а POST /books
  берёт `{{token}}`. Переменная живёт только внутри одного запуска, поэтому шаги 3 и 4 выполнены одним
  запуском newman с двумя `--folder`.
- **VS Code нет.** Программа просматривается `cat`, `grep`, `sed`. Файл `add100RandomBooks.py`
  в ВМ поставляется готовым; оригинал Cisco не опубликован, поэтому файл написан заново по описанию
  методички (те же имена APIHOST, LOGIN, PASSWORD, getAuthToken, addBook, apiKey, те же вызовы и
  вывод `Book {...} added.`). Диапазон `range(4, 104)`, как в тексте методички (в копии ВМ было
  `range(4, 105)`, см. Instructor Note). Книги 4 и 5 при этом перезаписываются случайными данными.
- Faker и requests в ВМ предустановлены, здесь ставятся в `prepare.sh` (на Python 3.8 pip выбирает
  Faker 35.x). Поэтому число методов в списке `fake.` + Tab отличается от 252 в методичке.
- В `~/.inputrc` добавлено `set page-completions off`, чтобы список `fake.` + Tab Tab выводился
  целиком, без пейджера `--More--`. На вопрос «Display all N possibilities? (y or n)» отправляется
  пробел (readline считает его ответом «y»). После списка ввод `fake.` сбрасывается Ctrl+C
  (KeyboardInterrupt).
- Обновление страницы сайта в Chromium (Part 4 Step 8b) заменено скриптом `list_all_books.py`: он
  читает книги так же, как JavaScript страницы (по `Link: rel="next"`, при 429 ждёт `Retry-After`).
- Перед каждым GET /books в Parts 2-3 стоит `pause: 2`: так в одно 10-секундное окно попадает не
  больше 5 запросов и ограничение частоты не срабатывает. Ответ 429 виден только в `list_all_books.py`.
- Дополнительно проверен ответ на вопрос методички: копия скрипта с `range(104, 204)`, затем итоговый
  подсчёт книг.

## Соответствие шагов

| Методичка | Шаги сценария |
|-----------|---------------|
| Part 1 | `p1_env`, `p1_simulator` |
| Part 2 Steps 1-4 | `p2s1_hosts` ... `p2s4_get_books_doc` |
| Part 2 Steps 5-7 | `p2s5_try_it_out`, `p2s6_curl_books`, `p2s7_include_isbn` |
| Part 2 Step 8 | `p2s8_login_401`, `p2s8_login`, `p2s8_authorize_scheme`, `p2s8_authorize` |
| Part 2 Steps 9-13 | `p2s9_post_book4` ... `p2s13_list_books` |
| Part 3 Steps 1-6 | `p3s1_newman` ... `p3s6_newman_params` |
| Part 4 Steps 1-7 | `p4s1_cd` ... `p4s7_main` |
| Part 4 Step 8, Note | `p4s8_run`, `p4s8_list_script`, `p4s8_list_all`, `p4s8_note_page` |
| Вопрос | `pq_more_books_script`, `pq_more_books_run`, `final_count` |

Ожидаемые итоги: 104 книги после Part 4 (id 0..103), 204 после проверки ответа на вопрос.

## Что проверить в результатах прогона

- `prepare.sh`: установились ли Node.js 20 из NodeSource (Node 20 вне поддержки с 2026-04; при сбое
  срабатывает запасной архив с nodejs.org), `newman@6` и Faker.
- Шаг `p4s2_s3_faker_repl`: появились ли «Display all N possibilities? (y or n)», полный список и
  KeyboardInterrupt (в `steps.json` не должно быть `interact_timeouts`).
- Шаг `p2s8_login`: запрос пароля curl и тело с токеном.
- Шаги Parts 2-3 без ответов 429.
- Вывод newman содержит символы Unicode (→ ★ ↑ ↓ ┌ │ └). В шрифте Consolas нет ★, при отрисовке PNG
  этот символ берётся из запасного шрифта.
