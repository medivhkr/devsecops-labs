#!/usr/bin/env python3
"""Сбор материалов каждой работы в labs/<работа>/materials/ и README.md работы.

materials/ содержит итоговые версии файлов, созданных в ходе работы (плейбуки, inventory,
скрипты, testbed, резервные копии и т.п.). Источник - каталог outputs*/files/, то есть файлы,
снятые со стенда после реального выполнения сценария. Файлы стенда из src/ (симуляторы,
коллекции Postman, скрипты топологий) копируются в materials/stand/.

  python tools/make_materials.py            # все работы, у которых есть протокол
"""

import json
import os
import re
import shutil

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SLUG = "medivhkr/devsecops-labs"
SKIP = {"__pycache__", ".pytest_cache"}
TEXT_EXT = {".py", ".yml", ".yaml", ".json", ".txt", ".cfg", ".conf", ".xml", ".sh", ".md", ".rules", ""}


def copytree(src, dst):
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SKIP]
        rel = os.path.relpath(root, src)
        for f in files:
            if f.endswith(".pyc"):
                continue
            os.makedirs(os.path.join(dst, rel), exist_ok=True)
            shutil.copy2(os.path.join(root, f), os.path.join(dst, rel, f))


def tree_lines(base, rel_prefix):
    lines = []
    for root, dirs, files in os.walk(base):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(root, f)
            rel = os.path.relpath(p, base).replace("\\", "/")
            size = os.path.getsize(p)
            lines.append("- [{0}]({1}/{0}) ({2})".format(rel, rel_prefix, human(size)))
    return lines


def human(n):
    return "{} Б".format(n) if n < 1024 else "{:.1f} КБ".format(n / 1024).replace(".", ",")


def run_link(lab_dir, outdir):
    p = os.path.join(lab_dir, outdir, "RUN.md")
    if os.path.exists(p):
        m = re.search(r"https://github\.com/\S+/actions/runs/\d+", open(p, encoding="utf-8").read())
        return m.group(0) if m else None
    return None


def main():
    labs_root = os.path.join(REPO, "labs")
    for folder in sorted(os.listdir(labs_root)):
        lab_dir = os.path.join(labs_root, folder)
        m = re.match(r"\d+-([\d.]+)-", folder)
        if not m or not os.path.isdir(lab_dir):
            continue
        lab = m.group(1)
        outs = sorted(d for d in os.listdir(lab_dir) if d.startswith("outputs") and os.path.isdir(os.path.join(lab_dir, d)))
        if not outs:
            continue
        mat = os.path.join(lab_dir, "materials")
        shutil.rmtree(mat, ignore_errors=True)
        for o in outs:
            files = os.path.join(lab_dir, o, "files")
            if os.path.isdir(files):
                copytree(files, mat if o == "outputs" else os.path.join(mat, o.split("-", 1)[1]))
        src = os.path.join(lab_dir, "src")
        if os.path.isdir(src):
            copytree(src, os.path.join(mat, "stand"))

        rep = os.path.join(lab_dir, "report", "report.json")
        title, goal = "", ""
        if os.path.exists(rep):
            spec = json.load(open(rep, encoding="utf-8"))
            title = " ".join(spec.get("title_ru_lines", []))
            for b in spec["blocks"]:
                if b.get("t") == "label":
                    goal = b["text"]
                    break
        md = ["# Лабораторная работа {}{}".format(lab, ": " + title if title else ""), ""]
        if goal:
            md += ["Цель работы: " + goal, ""]
        md += ["## Отчёт", ""]
        if os.path.exists(os.path.join(REPO, "reports", "lab-{}.pdf".format(lab))):
            md += ["- [PDF](../../reports/lab-{0}.pdf) · [DOCX](../../reports/lab-{0}.docx)".format(lab), ""]
        else:
            md += ["- готовится", ""]
        md += ["## Материалы работы", "",
               "Итоговые версии файлов, созданных при выполнении работы (сняты со стенда после прогона):", ""]
        md += tree_lines(mat, "materials") or ["- нет"]
        md += ["", "## Как выполнялась работа", ""]
        md.append("- [scenario.yml](scenario.yml): команды работы в порядке методички")
        for extra, desc in (("scenario-osm.yml", "вариант сценария на OpenStreetMap"),
                            ("prepare.sh", "подготовка стенда до начала записи"),
                            ("NOTES.md", "соответствие шагов методички и отличия от неё"),
                            ("NOTES-osm.md", "заметки к варианту OpenStreetMap")):
            if os.path.exists(os.path.join(lab_dir, extra)):
                md.append("- [{}]({}): {}".format(extra, extra, desc))
        prep = os.path.join(lab_dir, "prepare.sh")
        if os.path.exists(prep) and "start-csr1kv.sh" in open(prep, encoding="utf-8").read():
            md.append("- [lab-env/start-csr1kv.sh](../../lab-env/start-csr1kv.sh) и "
                      "[tools/csr1kv_emulator](../../tools/csr1kv_emulator): маршрутизатор CSR1kv (эмулятор IOS XE)")
        for o in outs:
            label = "протокол терминала" if o == "outputs" else "протокол ({})".format(o.split("-", 1)[1].upper())
            link = run_link(lab_dir, o)
            md.append("- [{}/transcript.txt]({}/transcript.txt): {}{}".format(
                o, o, label, ", [прогон в GitHub Actions]({})".format(link) if link else ""))
        open(os.path.join(lab_dir, "README.md"), "w", encoding="utf-8", newline="\n").write("\n".join(md) + "\n")
        print("{:8} materials: {} файлов".format(lab, sum(len(f) for _, _, f in os.walk(mat))))


if __name__ == "__main__":
    main()
