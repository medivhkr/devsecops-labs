#!/usr/bin/env python3
"""Повторная обработка "сырого" потока pty (raw.log) без повторного запуска стенда.

labrun сохраняет весь поток из псевдотерминала в raw.log. Этот скрипт прогоняет тот же
сценарий по сохранённому потоку и заново формирует steps/*.txt и transcript.txt
(например, после исправления разбора приглашений). Команды при этом не выполняются.

  python tools/labrun/replay.py labs/<lab>/scenario.yml raw.log --out out/<lab>
"""

import argparse
import os
import re
import sys
import types

# заглушки для Windows: pwd и pexpect нужны labrun только при реальном запуске
pwd_stub = types.ModuleType("pwd")
pwd_stub.getpwnam = lambda name: types.SimpleNamespace(pw_dir="/home/" + name, pw_uid=1000, pw_gid=1000)
sys.modules.setdefault("pwd", pwd_stub)


class _Timeout(Exception):
    pass


class _EOF(Exception):
    pass


pexpect_stub = types.ModuleType("pexpect")
pexpect_stub.TIMEOUT = _Timeout
pexpect_stub.EOF = _EOF
sys.modules["pexpect"] = pexpect_stub

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import labrun  # noqa: E402


class FakeChild(object):
    """Отдаёт сохранённый поток так же, как его отдавал бы pexpect."""

    def __init__(self, stream):
        self.s = stream
        self.pos = 0
        self.before = self.after = ""
        self.match = None

    def sendline(self, _):
        pass

    send = sendline

    def sendcontrol(self, _):
        pass

    def expect(self, pattern, timeout=None):
        if pattern is _EOF:
            raise _EOF()
        rx = pattern if hasattr(pattern, "search") else re.compile(pattern)
        m = rx.search(self.s, self.pos)
        if not m:
            raise _Timeout()
        self.before = self.s[self.pos:m.start()]
        self.after = m.group(0)
        self.match = m
        self.pos = m.end()
        return 0

    def read_nonblocking(self, size=1, timeout=None):
        if self.pos >= len(self.s):
            raise _EOF()
        ch = self.s[self.pos]
        self.pos += 1
        return ch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("raw")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    import yaml
    sc = yaml.safe_load(open(args.scenario, encoding="utf-8"))
    stream = open(args.raw, encoding="utf-8", errors="replace", newline="").read()
    runner = labrun.LabRunner(sc, args.out, "devasc")
    runner.raw.close()
    os.remove(os.path.join(args.out, "raw.log"))

    class _NullLog(object):
        def write(self, *_):
            pass

        def close(self):
            pass

    runner.raw = _NullLog()
    child = FakeChild(stream)

    def start_shell():
        runner.child = child
        child.expect("__LABRUN_SYNC__\r?\n")
        code, body, prompt = runner.wait_prompt(30)
        runner.pending = prompt

    runner.start_shell = start_shell
    # шаги host и write_file при повторе не выполняются
    sc["steps"] = [s if "cmd" in s else dict(s, _skip=True) for s in sc["steps"]]
    orig = runner.run_step

    def run_step(i, step):
        if step.get("_skip"):
            return
        orig(i, step)

    runner.run_step = run_step
    runner.collect = lambda: None
    runner.run()


if __name__ == "__main__":
    main()
