# Лабораторная работа 7.6.3: Автоматизированное тестирование с использованием pyATS и Genie

Выполнил: студент группы БИС-2-23 Азаматов Адис.

Цель работы: изучить основы автоматизированного тестирования сетевых устройств с помощью pyATS и Genie: установить их в виртуальное окружение Python, запустить пример тестового задания, разобрать вывод команд маршрутизатора CSR1kv в структурированный вид и сравнить два состояния его конфигурации.

## Отчёт

- [PDF](../../reports/lab-7.6.3.pdf) · [DOCX](../../reports/lab-7.6.3.docx)

## Материалы работы

Итоговые версии файлов, созданных при выполнении работы (сняты со стенда после прогона):

- [csr1kv.log](materials/csr1kv.log) (3,6 КБ)
- [diff_CSR1kv_show-ipv6-interface-gig-1_parsed.txt](materials/diff_CSR1kv_show-ipv6-interface-gig-1_parsed.txt) (413 Б)
- [pyvenv.cfg](materials/pyvenv.cfg) (70 Б)
- [verify-ipv6-1/CSR1kv_show-ipv6-interface-gig-1_console.txt](materials/verify-ipv6-1/CSR1kv_show-ipv6-interface-gig-1_console.txt) (758 Б)
- [verify-ipv6-1/CSR1kv_show-ipv6-interface-gig-1_parsed.txt](materials/verify-ipv6-1/CSR1kv_show-ipv6-interface-gig-1_parsed.txt) (877 Б)
- [verify-ipv6-1/connection_CSR1kv.txt](materials/verify-ipv6-1/connection_CSR1kv.txt) (4,7 КБ)
- [verify-ipv6-2/CSR1kv_show-ipv6-interface-gig-1_console.txt](materials/verify-ipv6-2/CSR1kv_show-ipv6-interface-gig-1_console.txt) (741 Б)
- [verify-ipv6-2/CSR1kv_show-ipv6-interface-gig-1_parsed.txt](materials/verify-ipv6-2/CSR1kv_show-ipv6-interface-gig-1_parsed.txt) (846 Б)
- [verify-ipv6-2/connection_CSR1kv.txt](materials/verify-ipv6-2/connection_CSR1kv.txt) (4,7 КБ)
- [yaml/testbed.yml](materials/yaml/testbed.yml) (319 Б)

## Как выполнялась работа

- [scenario.yml](scenario.yml): команды работы в порядке методички
- [prepare.sh](prepare.sh): подготовка стенда до начала записи
- [lab-env/start-csr1kv.sh](../../lab-env/start-csr1kv.sh) и [tools/csr1kv_emulator](../../tools/csr1kv_emulator): маршрутизатор CSR1kv (эмулятор IOS XE)
- [outputs/transcript.txt](outputs/transcript.txt): протокол терминала, [прогоны в GitHub Actions](https://github.com/medivhkr/devsecops-labs/actions/workflows/lab-7.6.3.yml)
