# Лабораторная работа 7.0.3: Установка виртуальной машины CSR1000v

Выполнил: студент группы БИС-2-23 Азаматов Адис.

Цель работы: подготовить виртуальный маршрутизатор CSR1000v для следующих лабораторных работ курса и проверить связь с ним из ВМ DEVASC: доступность по сети, вход по SSH и выполнение команд IOS XE.

## Отчёт

- [PDF](../../reports/lab-7.0.3.pdf) · [DOCX](../../reports/lab-7.0.3.docx)

## Материалы работы

Итоговые версии файлов, созданных при выполнении работы (сняты со стенда после прогона):

- [csr1kv.log](materials/csr1kv.log) (779 Б)

## Как выполнялась работа

- [scenario.yml](scenario.yml): команды работы в порядке методички
- [prepare.sh](prepare.sh): подготовка стенда до начала записи
- [lab-env/start-csr1kv.sh](../../lab-env/start-csr1kv.sh) и [tools/csr1kv_emulator](../../tools/csr1kv_emulator): маршрутизатор CSR1kv (эмулятор IOS XE)
- [outputs/transcript.txt](outputs/transcript.txt): протокол терминала, [прогоны в GitHub Actions](https://github.com/medivhkr/devsecops-labs/actions/workflows/lab-7.0.3.yml)
