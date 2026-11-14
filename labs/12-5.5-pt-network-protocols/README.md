# Лабораторная работа 5.5: Изучение сетевых протоколов

Выполнил: студент группы БИС-2-23 Азаматов Адис.

Цель работы: познакомиться с сетевыми службами DNS, DHCP, NTP, SSH, SNMP, HTTPS, электронной почты и FTP, включить и настроить их на серверах и сетевых устройствах учебной топологии и проверить работу каждой службы с клиентских устройств.

## Отчёт

- [PDF](../../reports/lab-5.5.pdf) · [DOCX](../../reports/lab-5.5.docx)

## Материалы работы

Итоговые версии файлов, созданных при выполнении работы (сняты со стенда после прогона):

- [Corporate-chrony.conf](materials/Corporate-chrony.conf) (345 Б)
- [DEVASC-Server.conf](materials/DEVASC-Server.conf) (791 Б)
- [Example-Server.conf](materials/Example-Server.conf) (549 Б)
- [R3-snmpd.conf](materials/R3-snmpd.conf) (276 Б)
- [dnsmasq.leases](materials/dnsmasq.leases) (68 Б)
- [dnsmasq.d/Corporate-dhcp.conf](materials/dnsmasq.d/Corporate-dhcp.conf) (528 Б)
- [dnsmasq.d/Corporate-dns.conf](materials/dnsmasq.d/Corporate-dns.conf) (238 Б)
- [dnsmasq.d/Example-Server-dns.conf](materials/dnsmasq.d/Example-Server-dns.conf) (309 Б)
- [labnet/Corporate-ftp.ini](materials/labnet/Corporate-ftp.ini) (314 Б)
- [labnet/Example-Server-email.ini](materials/labnet/Example-Server-email.ini) (154 Б)
- [netns/PC-A/hosts](materials/netns/PC-A/hosts) (20 Б)
- [netns/PC-A/nsswitch.conf](materials/netns/PC-A/nsswitch.conf) (107 Б)
- [netns/PC-A/resolv.conf](materials/netns/PC-A/resolv.conf) (23 Б)
- [netns/PC-B/hosts](materials/netns/PC-B/hosts) (20 Б)
- [netns/PC-B/nsswitch.conf](materials/netns/PC-B/nsswitch.conf) (107 Б)
- [netns/PC-B/resolv.conf](materials/netns/PC-B/resolv.conf) (52 Б)
- [pt-lab/S2.log](materials/pt-lab/S2.log) (1,7 КБ)
- [pt-lab/S2.out](materials/pt-lab/S2.out) (1,7 КБ)
- [pt-lab/email.log](materials/pt-lab/email.log) (6,0 КБ)
- [pt-lab/ftp.log](materials/pt-lab/ftp.log) (992 Б)
- [pt-lab/nginx-DEVASC-Server.access.log](materials/pt-lab/nginx-DEVASC-Server.access.log) (343 Б)
- [pt-lab/nginx-DEVASC-Server.error.log](materials/pt-lab/nginx-DEVASC-Server.error.log) (0 Б)
- [pt-lab/nginx-Example-Server.access.log](materials/pt-lab/nginx-Example-Server.access.log) (172 Б)
- [pt-lab/nginx-Example-Server.error.log](materials/pt-lab/nginx-Example-Server.error.log) (0 Б)
- [pt-lab/snmpd-R3.log](materials/pt-lab/snmpd-R3.log) (41,9 КБ)
- [pt-mail/www.example.com/Student1/new/1794656183015898533.15b82fcd.eml](materials/pt-mail/www.example.com/Student1/new/1794656183015898533.15b82fcd.eml) (328 Б)
- [pt-mail/www.example.com/Student2/new/1794656183501910943.efbb3a21.eml](materials/pt-mail/www.example.com/Student2/new/1794656183501910943.efbb3a21.eml) (450 Б)
- [pt-protocols/DEVASC-Server/devasc.crt](materials/pt-protocols/DEVASC-Server/devasc.crt) (1,1 КБ)
- [pt-protocols/PC-A/asa842-k8.bin](materials/pt-protocols/PC-A/asa842-k8.bin) (5441,0 КБ)
- [pt-protocols/PC-A/reply-to-Student2.eml](materials/pt-protocols/PC-A/reply-to-Student2.eml) (295 Б)
- [pt-protocols/PC-A/sampleFile.txt](materials/pt-protocols/PC-A/sampleFile.txt) (26 Б)
- [pt-protocols/PC-B/email-to-Student1.eml](materials/pt-protocols/PC-B/email-to-Student1.eml) (182 Б)
- [stand/dhcp.sh](materials/stand/dhcp.sh) (1,9 КБ)
- [stand/email_server.py](materials/stand/email_server.py) (13,2 КБ)
- [stand/ftp_server.py](materials/stand/ftp_server.py) (5,1 КБ)
- [stand/pt_console.py](materials/stand/pt_console.py) (2,2 КБ)
- [stand/s2_switch.py](materials/stand/s2_switch.py) (20,7 КБ)

## Как выполнялась работа

- [scenario.yml](scenario.yml): команды работы в порядке методички
- [prepare.sh](prepare.sh): подготовка стенда до начала записи
- [NOTES.md](NOTES.md): соответствие шагов методички и отличия от неё
- [outputs/transcript.txt](outputs/transcript.txt): протокол терминала, [прогоны в GitHub Actions](https://github.com/medivhkr/devsecops-labs/actions/workflows/lab-5.5.yml)
