#!/usr/bin/env python3
"""labrun: запись терминальной сессии лабораторной работы по сценарию.

Сценарий (YAML) описывает шаги так, как их выполняет студент: команды
в терминале, ответы на интерактивные запросы, создание файлов "в редакторе".
Команды выполняются в настоящей интерактивной оболочке bash в псевдотерминале
(pexpect), поэтому в протоколе видно всё, что увидел бы человек: приглашение,
эхо введённых символов, вывод программ, запросы пароля и т.д.

Запускать от root: оболочка студента открывается через `su - <user>`.

Результат:
  OUT/transcript.txt   - вся сессия целиком (очищенная от escape-последовательностей)
  OUT/steps/NN_id.txt  - вывод каждого шага отдельно
  OUT/steps.json       - метаданные шагов: команда, код возврата, время
  OUT/raw.log          - "сырой" поток из pty для аудита
  OUT/files/...        - копии файлов и каталогов, перечисленных в collect

Виды шагов:
  cmd:        команда в терминале студента (+ interact: [{expect, send}])
  write_file: файл, который студент создаёт в редакторе (VS Code)
  host:       служебная команда от root, в протокол не попадает
"""

import argparse
import datetime as dt
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
import time

import pexpect
import yaml

MARK_RE = re.compile(r"\x1b\]0;LABRUN:(\d+)\x07")
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][A-Za-z0-9]|\x1b[=>78]|[\x0e\x0f]")


WIDTH = 100  # ширина терминала, как у обычного окна эмулятора терминала
VENV_PREFIX_RE = re.compile(r"^\([\w.-]+\) ?$")


def screen_text(raw, width=WIDTH):
    """Возвращает текст так, как он выглядит на экране терминала шириной width.

    Используется эмулятор VT100 pyte: учитываются перенос длинных строк, \\r, \\b,
    стирание строки, перемещения курсора (readline, more, индикаторы прогресса).
    """
    raw = MARK_RE.sub("", raw)
    try:
        import pyte
    except ImportError:
        return clean(raw)
    height = raw.count("\n") + raw.count("\r") // 4 + 60
    height += sum(len(l) // width for l in raw.split("\n"))
    screen = pyte.Screen(width, max(height, 60))
    stream = pyte.Stream(screen)
    stream.feed(raw)
    lines = [l.rstrip() for l in screen.display]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def clean(text):
    """Удаляет escape-последовательности и применяет \\r и \\b так, как это сделал бы терминал."""
    text = MARK_RE.sub("", text)
    text = re.sub(r"\x1b\[0?K", "\x1e", text)  # "стереть до конца строки" обрабатываем ниже
    text = ANSI_RE.sub("", text)
    out_lines = []
    for line in text.split("\n"):
        line = line.rstrip("\r")
        buf = []
        col = 0
        for ch in line:
            if ch == "\r":
                col = 0
            elif ch == "\x1e":
                del buf[col:]
            elif ch == "\b":
                col = max(0, col - 1)
            elif ch in "\x07\x00":
                continue
            else:
                if col < len(buf):
                    buf[col] = ch
                else:
                    buf.append(ch)
                col += 1
        out_lines.append("".join(buf).rstrip())
    return "\n".join(out_lines)


class LabRunner(object):
    def __init__(self, scenario, out_dir, user):
        self.sc = scenario
        self.out = out_dir
        self.user = user
        self.home = os.path.expanduser("~" + user)
        os.makedirs(os.path.join(out_dir, "steps"), exist_ok=True)
        os.makedirs(os.path.join(out_dir, "files"), exist_ok=True)
        self.raw = open(os.path.join(out_dir, "raw.log"), "w", encoding="utf-8", errors="replace")
        self.meta = []
        self.transcript = []
        self.child = None
        self.pending = ""

    def expand(self, path):
        return self.home + path[1:] if path.startswith("~") else path

    def start_shell(self):
        # Оболочка запускается сразу от имени пользователя (без su): тогда bash является лидером
        # сессии в pty, работает управление заданиями и Ctrl+C получает только текущая команда.
        pw = pwd.getpwnam(self.user)
        env = {
            "HOME": pw.pw_dir, "USER": self.user, "LOGNAME": self.user, "SHELL": "/bin/bash",
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "TERM": "xterm", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "COLUMNS": str(WIDTH), "LINES": "50",
        }

        def drop_privileges():
            if os.geteuid() == 0:
                os.setgid(pw.pw_gid)
                os.initgroups(self.user, pw.pw_gid)
                os.setuid(pw.pw_uid)

        self.child = pexpect.spawn("/bin/bash", ["--noprofile", "--norc", "-i"], env=env, cwd=pw.pw_dir,
                                   encoding="utf-8", codec_errors="replace", dimensions=(50, WIDTH), timeout=600,
                                   preexec_fn=drop_privileges)
        self.child.logfile_read = self.raw
        time.sleep(1.0)
        init = [
            "bind 'set enable-bracketed-paste off' 2>/dev/null",
            "export LANG=C.UTF-8 LC_ALL=C.UTF-8 TERM=xterm COLUMNS={}".format(WIDTH),
            "stty cols {} rows 50".format(WIDTH),
            "cd ~",
        ]
        init += list(self.sc.get("shell_init", []) or [])
        init.append("export PS1='\\[\\e]0;LABRUN:$?\\a\\]\\u@\\h:\\w\\$ '")
        for line in init:
            self.child.sendline(line)
        self.child.sendline('echo __LAB""RUN_SYNC__')
        self.child.expect("__LABRUN_SYNC__\r?\n", timeout=60)
        code, body, prompt = self.wait_prompt(30)
        self.pending = clean(prompt)

    def wait_prompt(self, timeout):
        """Ждёт приглашение оболочки. Возвращает (код возврата, вывод до приглашения, строка приглашения)."""
        self.child.expect(MARK_RE, timeout=timeout)
        before = self.child.before
        code = int(self.child.match.group(1))
        tail = ""
        end = time.time() + 3
        while time.time() < end and not (tail.endswith("$ ") or tail.endswith("# ")):
            try:
                tail += self.child.read_nonblocking(1000, timeout=0.3)
            except pexpect.TIMEOUT:
                continue
            except pexpect.EOF:
                break
        # приглашение начинается с маркера; перед ним может стоять только префикс venv "(name) "
        idx = before.rfind("\n")
        last = clean(before[idx + 1:]) if idx >= 0 else clean(before)
        if VENV_PREFIX_RE.match(last):
            body = before[:idx + 1] if idx >= 0 else ""
            return code, body, last.rstrip() + " " + tail
        return code, before, tail

    def chown_path(self, path):
        cur = os.path.dirname(path)
        subprocess.call(["chown", "{0}:{0}".format(self.user), path])
        while cur.startswith(self.home) and cur != self.home:
            subprocess.call(["chown", "{0}:{0}".format(self.user), cur])
            cur = os.path.dirname(cur)

    def run_step(self, idx, step):
        sid = step.get("id", "step{:02d}".format(idx))
        rec = {"n": idx, "id": sid, "title": step.get("title", ""), "start": dt.datetime.utcnow().isoformat() + "Z"}
        t0 = time.time()

        if "write_file" in step:
            wf = step["write_file"]
            path = self.expand(wf["path"])
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(wf["content"])
            if "mode" in wf:
                os.chmod(path, int(str(wf["mode"]), 8))
            self.chown_path(path)
            rec.update({"type": "file", "path": wf["path"], "content": wf["content"]})
            self.meta.append(rec)
            print("[{:02d}] write {}".format(idx, wf["path"]), flush=True)
            return

        if "host" in step:
            res = subprocess.run(step["host"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 universal_newlines=True, timeout=step.get("timeout", 900))
            rec.update({"type": "host", "cmd": step["host"], "exit": res.returncode, "output": res.stdout[-6000:]})
            self.meta.append(rec)
            print("[{:02d}] host: {} -> {}".format(idx, step["host"][:70], res.returncode), flush=True)
            if res.returncode != 0:
                print(res.stdout[-3000:], file=sys.stderr)
            if step.get("sleep"):
                time.sleep(step["sleep"])
            return

        cmd = step["cmd"]
        prompt_text = self.pending
        if step.get("pause"):
            time.sleep(step["pause"])
        self.child.sendline(cmd)
        chunks = []
        for it in step.get("interact", []) or []:
            try:
                self.child.expect(it["expect"], timeout=it.get("timeout", 300))
            except pexpect.TIMEOUT:
                rec.setdefault("interact_timeouts", []).append(it["expect"])
                if it.get("optional"):
                    continue
                break
            chunks.append(self.child.before + self.child.after)
            if it.get("delay"):
                time.sleep(it["delay"])
            if "send" in it:
                if it.get("raw"):
                    self.child.send(it["send"])
                else:
                    self.child.sendline(it["send"])
            if it.get("sendcontrol"):
                self.child.sendcontrol(it["sendcontrol"])
        try:
            code, body, prompt = self.wait_prompt(step.get("timeout", 900))
        except pexpect.TIMEOUT:
            rec["timeout"] = True
            chunks.append(self.child.before)
            self.child.sendcontrol("c")
            code, body, prompt = self.wait_prompt(120)
        chunks.append(body)
        text = screen_text(prompt_text + "".join(chunks))
        next_prompt = clean(prompt)
        self.pending = next_prompt
        text = text.rstrip() + "\n"
        if step.get("show_next_prompt", False):
            text += next_prompt.rstrip() + "\n"
        rec.update({"type": "cmd", "cmd": cmd, "exit": code, "seconds": round(time.time() - t0, 2)})
        if step.get("expect_exit") is not None and code != step["expect_exit"]:
            rec["unexpected_exit"] = True
        fname = "{:02d}_{}.txt".format(idx, sid)
        with open(os.path.join(self.out, "steps", fname), "w", encoding="utf-8") as fh:
            fh.write(text)
        rec["file"] = "steps/" + fname
        self.transcript.append(text)
        self.meta.append(rec)
        print("[{:02d}] {} -> exit {} ({:.1f}s)".format(idx, cmd[:90], code, time.time() - t0), flush=True)

    def collect(self):
        for item in self.sc.get("collect", []) or []:
            src = self.expand(item)
            name = os.path.basename(src.rstrip("/"))
            dst = os.path.join(self.out, "files", name)
            try:
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True, symlinks=True,
                                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "lib", "lib64", "bin",
                                                                  "include", "share", ".git"))
                elif os.path.exists(src):
                    shutil.copy2(src, dst)
            except Exception as exc:  # noqa: BLE001
                print("collect failed:", src, exc, file=sys.stderr)

    def run(self):
        self.start_shell()
        for i, step in enumerate(self.sc["steps"], 1):
            self.run_step(i, step)
        # итоговая строка приглашения, как в конце любого блока в методичке
        if self.transcript:
            self.transcript[-1] = self.transcript[-1].rstrip() + "\n" + self.pending.rstrip() + "\n"
        try:
            self.child.sendline("exit")
            self.child.expect(pexpect.EOF, timeout=10)
        except Exception:
            pass
        self.collect()
        with open(os.path.join(self.out, "transcript.txt"), "w", encoding="utf-8") as fh:
            fh.write("".join(self.transcript))
        with open(os.path.join(self.out, "steps.json"), "w", encoding="utf-8") as fh:
            json.dump({"lab": self.sc.get("lab"), "title": self.sc.get("title"),
                       "finished": dt.datetime.utcnow().isoformat() + "Z", "steps": self.meta}, fh,
                      ensure_ascii=False, indent=2)
        self.raw.close()
        problems = [m for m in self.meta if m.get("timeout") or m.get("unexpected_exit") or m.get("interact_timeouts")]
        for m in problems:
            print("WARNING:", json.dumps(m, ensure_ascii=False)[:400], file=sys.stderr)
        return 1 if problems and self.sc.get("strict") else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("--out", required=True)
    ap.add_argument("--user", default="devasc")
    args = ap.parse_args()
    with open(args.scenario, encoding="utf-8") as fh:
        sc = yaml.safe_load(fh)
    sys.exit(LabRunner(sc, args.out, args.user).run())


if __name__ == "__main__":
    main()
