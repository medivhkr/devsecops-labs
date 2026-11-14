#!/usr/bin/env python3
"""Сборка всех отчётов (DOCX + PDF) и автоматические проверки результата.

  python tools/report-builder/build_all.py [--qa-dir DIR] [папки...]

Проверки по PDF: число страниц, неразрешённые ссылки (??), остатки разметки (**, `),
подписи рисунков/таблиц с точкой в конце, пустые страницы. Для визуальной проверки
страницы сохраняются в PNG (--qa-dir).
"""

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))


def check_pdf(pdf, qa_dir=None, dpi=80):
    import pymupdf
    doc = pymupdf.open(pdf)
    issues = []
    for i, page in enumerate(doc):
        text = page.get_text()
        if "??" in text:
            issues.append("p{}: '??' (неразрешённая ссылка)".format(i + 1))
        if re.search(r"\*\*|`", text):
            issues.append("p{}: остаток markdown-разметки".format(i + 1))
        for m in re.finditer(r"^(Рисунок|Таблица|Листинг) [\dА-Я.]+ – .*\.$", text, re.M):
            issues.append("p{}: точка в конце подписи: {}".format(i + 1, m.group(0)[:60]))
        if i > 0 and len(text.strip()) < 15 and not page.get_images():
            issues.append("p{}: почти пустая страница".format(i + 1))
        if qa_dir:
            os.makedirs(qa_dir, exist_ok=True)
            page.get_pixmap(dpi=dpi).save(os.path.join(qa_dir, "p{:02d}.png".format(i + 1)))
    if qa_dir:
        contact_sheet(qa_dir, doc.page_count)
    return doc.page_count, issues


def contact_sheet(qa_dir, n, cols=5):
    """Все страницы отчёта на одном изображении для быстрого просмотра вёрстки."""
    from PIL import Image, ImageDraw
    pages = [Image.open(os.path.join(qa_dir, "p{:02d}.png".format(i + 1))) for i in range(n)]
    w, h = pages[0].size
    scale = 0.55
    tw, th = int(w * scale), int(h * scale)
    rows = (n + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + 10) + 10, rows * (th + 26) + 10), (200, 200, 200))
    d = ImageDraw.Draw(sheet)
    for i, p in enumerate(pages):
        x = 10 + (i % cols) * (tw + 10)
        y = 10 + (i // cols) * (th + 26)
        sheet.paste(p.resize((tw, th)), (x, y + 16))
        d.text((x, y), str(i + 1), fill=(0, 0, 0))
    sheet.save(os.path.join(qa_dir, "sheet.png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="*")
    ap.add_argument("--qa-dir", default=None)
    ap.add_argument("--no-build", action="store_true")
    args = ap.parse_args()
    folders = args.folders or sorted(f for f in os.listdir(os.path.join(REPO, "labs"))
                                     if os.path.exists(os.path.join(REPO, "labs", f, "report", "report.json")))
    summary = []
    for f in folders:
        spec = json.load(open(os.path.join(REPO, "labs", f, "report", "report.json"), encoding="utf-8"))
        lab = spec["lab_id"]
        if not args.no_build:
            r = subprocess.run([sys.executable, os.path.join(HERE, "build.py"), os.path.join(REPO, "labs", f)],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                               encoding="utf-8", errors="replace")
            if r.returncode != 0 or "WARN" in r.stdout:
                summary.append((lab, 0, ["сборка: " + r.stdout[-800:]]))
                continue
        pdf = os.path.join(REPO, "reports", "lab-{}.pdf".format(lab))
        qa = os.path.join(args.qa_dir, lab) if args.qa_dir else None
        pages, issues = check_pdf(pdf, qa)
        summary.append((lab, pages, issues))
    for lab, pages, issues in summary:
        print("{:8} страниц: {:3}  {}".format(lab, pages, "OK" if not issues else "; ".join(issues)))


if __name__ == "__main__":
    main()
