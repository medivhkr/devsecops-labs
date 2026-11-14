# Лабораторная работа 7.4.7: Использование Ansible для резервного копирования и настройки устройства

Выполнил: студент группы БИС-2-23 Азаматов Адис.

Цель работы: изучить основы использования Ansible для автоматизации простых задач управления сетевым устройством: настроить Ansible в ВМ DEVASC, создать резервную копию конфигурации маршрутизатора CSR1000v и настроить на нём IPv6-адресацию.

## Отчёт

- [PDF](../../reports/lab-7.4.7.pdf) · [DOCX](../../reports/lab-7.4.7.docx)

## Материалы работы

Итоговые версии файлов, созданных при выполнении работы (сняты со стенда после прогона):

- [csr1kv.log](materials/csr1kv.log) (3,6 КБ)
- [ansible-csr1000v/ansible.cfg](materials/ansible-csr1000v/ansible.cfg) (266 Б)
- [ansible-csr1000v/backup_cisco_router_playbook.yaml](materials/ansible-csr1000v/backup_cisco_router_playbook.yaml) (393 Б)
- [ansible-csr1000v/cisco_router_ipv6_config_playbook.yaml](materials/ansible-csr1000v/cisco_router_ipv6_config_playbook.yaml) (639 Б)
- [ansible-csr1000v/hosts](materials/ansible-csr1000v/hosts) (200 Б)
- [ansible-csr1000v/backups/show_run_CSR1kv.txt](materials/ansible-csr1000v/backups/show_run_CSR1kv.txt) (2,0 КБ)
- [ansible-csr1000v/host_vars/CSR1kv.yml](materials/ansible-csr1000v/host_vars/CSR1kv.yml) (442 Б)
- [ansible-csr1000v/ios_configurations/IPv6_output_CSR1kv.txt](materials/ansible-csr1000v/ios_configurations/IPv6_output_CSR1kv.txt) (67 Б)

## Как выполнялась работа

- [scenario.yml](scenario.yml): команды работы в порядке методички
- [prepare.sh](prepare.sh): подготовка стенда до начала записи
- [lab-env/start-csr1kv.sh](../../lab-env/start-csr1kv.sh) и [tools/csr1kv_emulator](../../tools/csr1kv_emulator): маршрутизатор CSR1kv (эмулятор IOS XE)
- [outputs/transcript.txt](outputs/transcript.txt): протокол терминала, [прогоны в GitHub Actions](https://github.com/medivhkr/devsecops-labs/actions/workflows/lab-7.4.7.yml)
