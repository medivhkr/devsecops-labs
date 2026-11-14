#!/usr/bin/env python3
"""Генерация README.md: таблица работ со ссылками на отчёты, протоколы и статус CI."""

import json
import os
import re

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SLUG = "medivhkr/devsecops-labs"
GH = "https://github.com/" + SLUG

MODULES = [
    ("1", "Модуль 1. Введение в курс"),
    ("3", "Модуль 3. Разработка и проектирование программного обеспечения"),
    ("4", "Модуль 4. Понимание и использование API"),
    ("5", "Модуль 5. Основы сетей"),
    ("7", "Модуль 7. Инфраструктура и автоматизация"),
]


def lab_rows():
    rows = []
    for folder in sorted(os.listdir(os.path.join(REPO, "labs"))):
        m = re.match(r"\d+-([\d.]+)-", folder)
        if not m:
            continue
        lab = m.group(1)
        rep = os.path.join(REPO, "labs", folder, "report", "report.json")
        title = ""
        if os.path.exists(rep):
            spec = json.load(open(rep, encoding="utf-8"))
            title = " ".join(spec.get("title_ru_lines", []))
        pdf = "reports/lab-{}.pdf".format(lab)
        docx = "reports/lab-{}.docx".format(lab)
        has_pdf = os.path.exists(os.path.join(REPO, pdf))
        wf = "lab-{}.yml".format(lab)
        rows.append({
            "lab": lab, "folder": folder, "title": title, "module": lab.split(".")[0],
            "report": "[PDF]({}) · [DOCX]({})".format(pdf, docx) if has_pdf else "в работе",
            "protocol": "[протокол](labs/{}/outputs/transcript.txt)".format(folder)
            if os.path.exists(os.path.join(REPO, "labs", folder, "outputs", "transcript.txt")) else "—",
            "badge": "[![{0}]({1}/actions/workflows/{2}/badge.svg)]({1}/actions/workflows/{2})".format(lab, GH, wf)
            if os.path.exists(os.path.join(REPO, ".github", "workflows", wf)) else "",
        })
    return rows


def main():
    rows = lab_rows()
    out = []
    out.append("# Developer Security Operations: лабораторные работы\n")
    out.append("Кыргызский государственный технический университет им. И. Раззакова, Институт информационных технологий,")
    out.append("кафедра «Обеспечение безопасности информационных систем».\n")
    out.append("Выполнил: студент группы БИС-2-23 **Азаматов А.А.** Курс: Cisco DevNet Associate v1.0. Бишкек, 2026.\n")
    out.append("[![Проверки безопасности]({0}/actions/workflows/security.yml/badge.svg)]({0}/actions/workflows/security.yml)\n".format(GH))
    out.append("## Работы\n")
    for mod, name in MODULES:
        mrows = [r for r in rows if r["module"] == mod]
        if not mrows:
            continue
        out.append("### {}\n".format(name))
        out.append("| № | Тема | Отчёт | Протокол выполнения | Прогон в CI |")
        out.append("|---|------|-------|---------------------|-------------|")
        for r in mrows:
            out.append("| {lab} | {title} | {report} | {protocol} | {badge} |".format(**r))
        out.append("")
    out.append(open(os.path.join(REPO, "tools", "README_body.md"), encoding="utf-8").read())
    open(os.path.join(REPO, "README.md"), "w", encoding="utf-8", newline="\n").write("\n".join(out))
    print("README.md written,", len(rows), "labs")


if __name__ == "__main__":
    main()
