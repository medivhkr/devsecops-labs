#!/usr/bin/env python3
"""Сборка отчёта лабораторной работы: JSON -> рисунки терминала -> DOCX -> PDF.

  python tools/report-builder/build.py labs/14-7.4.7-ansible-backup-config [--no-pdf]

Ожидается labs/<lab>/report/report.json. Блоки "terminal" ссылаются на реальные
протоколы из labs/<lab>/outputs/steps/*.txt и превращаются в рисунки.
Результат: reports/lab-<id>.docx и reports/lab-<id>.pdf
"""

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
from render_terminal import render  # noqa: E402

PROMPT_CWD_RE = re.compile(r"^(?:\([\w.-]+\) )?([\w.-]+@[\w.-]+):([^$#]*)[$#]")


def select_lines(text, spec):
    lines = text.rstrip("\n").split("\n")
    if not spec:
        return lines
    out = []
    for part in str(spec).split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            a = int(a) if a else 1
            b = int(b) if b else len(lines)
            out.extend(lines[a - 1:b])
        else:
            out.append(lines[int(part) - 1])
    return out


def window_title(lines, default):
    for l in lines:
        m = PROMPT_CWD_RE.match(l)
        if m:
            return "{}: {}".format(m.group(1), m.group(2).strip() or "~")
    return default


def resolve(lab_dir):
    rep_dir = os.path.join(lab_dir, "report")
    spec = json.load(open(os.path.join(rep_dir, "report.json"), encoding="utf-8"))
    figs = os.path.join(rep_dir, "figs")
    os.makedirs(figs, exist_ok=True)
    n = 0
    for b in spec["blocks"]:
        if b.get("t") != "terminal":
            continue
        n += 1
        texts = []
        srcs = b["src"] if isinstance(b["src"], list) else [b["src"]]
        ranges = b.get("lines")
        ranges = ranges if isinstance(ranges, list) else [ranges] * len(srcs)
        for i, (src, rng) in enumerate(zip(srcs, ranges)):
            path = os.path.join(lab_dir, "outputs", src)
            texts.extend(select_lines(open(path, encoding="utf-8").read(), rng))
            if b.get("ellipsis_between") and i < len(srcs) - 1:
                texts.append("...")
        if b.get("append"):
            texts.extend(b["append"].split("\n"))
        title = b.get("title") or window_title(texts, "devasc@labvm: ~")
        fid = b.get("id") or "term{:02d}".format(n)
        png = os.path.join(figs, "{}.png".format(fid))
        render("\n".join(texts), title, png, cols=b.get("cols", 100))
        b["t"] = "figure"
        b["terminal"] = True
        b["image"] = os.path.relpath(png, rep_dir).replace("\\", "/")
        b.setdefault("id", fid)
    out = os.path.join(rep_dir, "report.resolved.json")
    json.dump(spec, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return spec, out


def export_pdf(docx, pdf):
    ps1 = os.path.join(HERE, "docx2pdf.ps1")
    subprocess.check_call(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1,
                           "-In", os.path.abspath(docx), "-Out", os.path.abspath(pdf)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lab_dir")
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args()
    lab_dir = os.path.abspath(args.lab_dir)
    spec, resolved = resolve(lab_dir)
    os.makedirs(os.path.join(REPO, "reports"), exist_ok=True)
    base = os.path.join(REPO, "reports", "lab-{}".format(spec["lab_id"]))
    subprocess.check_call(["node", os.path.join(HERE, "build-report.js"), resolved, base + ".docx"])
    if not args.no_pdf:
        export_pdf(base + ".docx", base + ".pdf")
        print("PDF", base + ".pdf")


if __name__ == "__main__":
    main()
