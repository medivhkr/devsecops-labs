# Лабораторная работа 7.4.8: Использование Ansible для автоматизации установки веб-сервера

Выполнил: студент группы БИС-2-23 Азаматов Адис.

Цель работы: настроить Ansible для связи с веб-сервером, автоматизировать установку Apache с помощью плейбука и создать плейбук, который устанавливает Apache с заданными параметрами.

## Отчёт

- [PDF](../../reports/lab-7.4.8.pdf) · [DOCX](../../reports/lab-7.4.8.docx)

## Материалы работы

Итоговые версии файлов, созданных при выполнении работы (сняты со стенда после прогона):

- [000-default.conf](materials/000-default.conf) (1,3 КБ)
- [apache_80.png](materials/apache_80.png) (169,0 КБ)
- [apache_8081.png](materials/apache_8081.png) (169,0 КБ)
- [ports.conf](materials/ports.conf) (276 Б)
- [ansible-apache/ansible.cfg](materials/ansible-apache/ansible.cfg) (186 Б)
- [ansible-apache/hosts](materials/ansible-apache/hosts) (74 Б)
- [ansible-apache/install_apache_options_playbook.yaml](materials/ansible-apache/install_apache_options_playbook.yaml) (724 Б)
- [ansible-apache/install_apache_playbook.yaml](materials/ansible-apache/install_apache_playbook.yaml) (334 Б)
- [ansible-apache/test_apache_playbook.yaml](materials/ansible-apache/test_apache_playbook.yaml) (99 Б)

## Как выполнялась работа

- [scenario.yml](scenario.yml): команды работы в порядке методички
- [prepare.sh](prepare.sh): подготовка стенда до начала записи
- [outputs/transcript.txt](outputs/transcript.txt): протокол терминала, [прогоны в GitHub Actions](https://github.com/medivhkr/devsecops-labs/actions/workflows/lab-7.4.8.yml)
