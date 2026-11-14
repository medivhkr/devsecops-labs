#!/usr/bin/env bash
# Подготовка стенда для лабораторной 3.3.11 (выполняется от root до записи, в протокол не попадает).
#  1) Исходное состояние, как в ВМ DEVASC до работы: каталога ~/labs/devnet-src/git-intro нет,
#     user.name и user.email в Git не заданы (их задаёт студент в Part 2).
#  2) Part 7: SSH-ключ развёртывания (deploy key с правом записи) репозитория medivhkr/devasc-study-team
#     из секрета DEVASC_STUDY_TEAM_KEY -> /home/devasc/.ssh/id_ed25519, ключи хоста github.com -> known_hosts.
#     Сам ключ никуда не выводится.
set -euo pipefail

U=devasc
H=/home/devasc
SSH_DIR="$H/.ssh"
KEY_FILE="$SSH_DIR/id_ed25519"
KNOWN_HOSTS="$SSH_DIR/known_hosts"
REMOTE="git@github.com:medivhkr/devasc-study-team.git"
# Опубликованные отпечатки ключей хоста github.com (ED25519 и RSA), docs.github.com
GITHUB_FP="SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU SHA256:uNiVztksCsDhcc0u9e8BujQXVUpKZIDTMczCvj3tD2s"

as_devasc() { (cd "$H" && sudo -u "$U" -H "$@"); }

echo "== Исходное состояние: нет git-intro, не заданы user.name и user.email"
mkdir -p "$H/labs/devnet-src"
rm -rf "$H/labs/devnet-src/git-intro" /tmp/devasc-study-team
chown -R "$U:$U" "$H/labs"
for k in user.name user.email; do
  as_devasc git config --global --unset-all "$k" 2>/dev/null || true
done

echo "== SSH: каталог $SSH_DIR"
install -d -m 700 -o "$U" -g "$U" "$SSH_DIR"
chmod 700 "$SSH_DIR"

echo "== SSH: ключ развёртывания"
KEY_OK=0
if [ -n "${DEVASC_STUDY_TEAM_KEY:-}" ]; then
  export DEVASC_STUDY_TEAM_KEY
  rm -f "$KEY_FILE" "$KEY_FILE.pub"
  install -m 600 -o "$U" -g "$U" /dev/null "$KEY_FILE"
  # Канонический вид ключа: секрет мог быть сохранён с CRLF, одной строкой с литеральными \n
  # или целиком в base64. Python читает ключ из окружения и пишет только в файл ключа.
  if ! python3 - > "$KEY_FILE" <<'PY'
import base64, os, re, sys, textwrap
key = os.environ.get("DEVASC_STUDY_TEAM_KEY", "").strip()
if "-----BEGIN" not in key:
    try:
        decoded = base64.b64decode("".join(key.split()), validate=True).decode("utf-8")
        if "-----BEGIN" in decoded:
            key = decoded.strip()
    except Exception:
        pass
key = key.replace("\\n", "\n").replace("\r", "")
m = re.search(r"-----BEGIN ([A-Z0-9 ]+)-----(.*?)-----END \1-----", key, re.S)
if not m:
    sys.exit(1)
label, body = m.group(1), re.sub(r"\s+", "", m.group(2))
width = 70 if label == "OPENSSH PRIVATE KEY" else 64
sys.stdout.write("-----BEGIN %s-----\n%s\n-----END %s-----\n"
                 % (label, "\n".join(textwrap.wrap(body, width)), label))
PY
  then
    printf '%s\n' "$DEVASC_STUDY_TEAM_KEY" | tr -d '\r' > "$KEY_FILE"
  fi
  chown "$U:$U" "$KEY_FILE"
  chmod 600 "$KEY_FILE"
  if ssh-keygen -y -P '' -f "$KEY_FILE" > "$KEY_FILE.pub" 2>/dev/null < /dev/null; then
    chown "$U:$U" "$KEY_FILE.pub"
    chmod 644 "$KEY_FILE.pub"
    echo "Ключ установлен: $(ssh-keygen -l -f "$KEY_FILE.pub" | awk '{print $1, $2, $NF}')"
    KEY_OK=1
  else
    rm -f "$KEY_FILE.pub"
    echo "WARNING: DEVASC_STUDY_TEAM_KEY не является незашифрованным закрытым ключом OpenSSH," \
         "шаги ssh -T, git push, git ls-remote и git clone завершатся ошибкой" >&2
  fi
else
  echo "WARNING: переменная DEVASC_STUDY_TEAM_KEY пуста: ключ не установлен," \
       "шаги ssh -T, git push, git ls-remote и git clone завершатся ошибкой" >&2
fi

echo "== SSH: ключи хоста github.com в known_hosts"
touch "$KNOWN_HOSTS"
sed -i '/^github\.com[ ,]/d' "$KNOWN_HOSTS"
scan="$(mktemp)"
for attempt in 1 2 3; do
  ssh-keyscan -T 10 -t ed25519,rsa github.com > "$scan" 2>/dev/null || true
  if grep -q '^github\.com ' "$scan"; then
    break
  fi
  echo "ssh-keyscan github.com: попытка $attempt не удалась" >&2
  sleep 5
done
if grep -q '^github\.com ' "$scan"; then
  grep '^github\.com ' "$scan" >> "$KNOWN_HOSTS"
  while read -r _bits fp _host type; do
    case " $GITHUB_FP " in
      *" $fp "*) echo "github.com $type $fp совпадает с опубликованным отпечатком GitHub" ;;
      *) echo "WARNING: github.com $type $fp не совпадает с опубликованными отпечатками GitHub" >&2 ;;
    esac
  done < <(ssh-keygen -l -f "$scan" 2>/dev/null || true)
else
  echo "WARNING: ssh-keyscan github.com не ответил; шаги с SSH будут ждать подтверждения" \
       "ключа хоста до тайм-аута шага" >&2
fi
rm -f "$scan"
chown "$U:$U" "$KNOWN_HOSTS"
chmod 644 "$KNOWN_HOSTS"

# Диагностика для журнала CI (только чтение): push пройдёт, только если репозиторий пуст.
if [ "$KEY_OK" = 1 ]; then
  echo "== GitHub: репозиторий $REMOTE должен быть пустым"
  err="$(mktemp)"
  if refs="$(as_devasc env GIT_SSH_COMMAND='ssh -o BatchMode=yes -o CheckHostIP=no -o ConnectTimeout=15' \
               timeout 60 git ls-remote "$REMOTE" 2>"$err")"; then
    if [ -z "$refs" ]; then
      echo "OK: репозиторий доступен по ключу и пуст"
    else
      echo "WARNING: репозиторий не пуст, git push будет отклонён." \
           "Пересоздайте пустой репозиторий и снова добавьте в него deploy key:" >&2
      printf '%s\n' "$refs" >&2
    fi
  else
    echo "WARNING: нет доступа к репозиторию по ключу:" >&2
    cat "$err" >&2
  fi
  rm -f "$err"
fi

echo "== Итог"
ls -la "$SSH_DIR"
