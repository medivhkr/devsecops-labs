# Протокол выполнения

Файлы в этом каталоге получены при реальном выполнении сценария `scenario.yml` в GitHub Actions.

- Прогоны сценария: https://github.com/medivhkr/devsecops-labs/actions/workflows/lab-5.5.yml
- Дата записи протокола (UTC): 2026-11-14T11:34:14Z

`transcript.txt` содержит сессию терминала целиком, `steps/` - вывод по шагам, `files/` - файлы, созданные в работе.

Закрытый ключ TLS `files/pt-protocols/DEVASC-Server/devasc.key`, созданный на стенде командой
`openssl genrsa`, из протокола удалён: закрытые ключи в репозиторий не переносятся (см. `.gitleaks.toml`).
Сертификат `devasc.crt` оставлен.
