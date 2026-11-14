# Лабораторная работа 4.9.2: Интеграция REST API в приложение на Python

Выполнил: студент группы БИС-2-23 Азаматов Адис.

Цель работы: научиться встраивать REST API в приложение на Python: по названиям двух мест сформировать URL запроса к службе построения маршрутов (в методичке это MapQuest Directions API), отправить запрос GET, разобрать ответ в формате JSON и вывести пользователю время в пути, расстояние и пошаговые указания. Приложение собирается поэтапно, и каждая новая функция проверяется запуском.

## Отчёт

- [PDF](../../reports/lab-4.9.2.pdf) · [DOCX](../../reports/lab-4.9.2.docx)

## Материалы работы

Итоговые версии файлов, созданных при выполнении работы (сняты со стенда после прогона):

- [osm/mapquest/osm_parse-json_1.py](materials/osm/mapquest/osm_parse-json_1.py) (1,4 КБ)
- [osm/mapquest/osm_parse-json_2.py](materials/osm/mapquest/osm_parse-json_2.py) (1,4 КБ)
- [osm/mapquest/osm_parse-json_3.py](materials/osm/mapquest/osm_parse-json_3.py) (1,4 КБ)
- [osm/mapquest/osm_parse-json_4.py](materials/osm/mapquest/osm_parse-json_4.py) (1,5 КБ)
- [osm/mapquest/osm_parse-json_5.py](materials/osm/mapquest/osm_parse-json_5.py) (2,2 КБ)
- [osm/mapquest/osm_parse-json_6.py](materials/osm/mapquest/osm_parse-json_6.py) (4,5 КБ)
- [osm/mapquest/osm_parse-json_7.py](materials/osm/mapquest/osm_parse-json_7.py) (6,9 КБ)

## Как выполнялась работа

- [scenario.yml](scenario.yml): команды работы в порядке методички
- [scenario-osm.yml](scenario-osm.yml): вариант сценария на OpenStreetMap
- [prepare.sh](prepare.sh): подготовка стенда до начала записи
- [NOTES.md](NOTES.md): соответствие шагов методички и отличия от неё
- [NOTES-osm.md](NOTES-osm.md): заметки к варианту OpenStreetMap
- [outputs-osm/transcript.txt](outputs-osm/transcript.txt): протокол (OSM), [прогоны в GitHub Actions](https://github.com/medivhkr/devsecops-labs/actions/workflows/lab-4.9.2-osm.yml)
