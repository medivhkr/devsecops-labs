#!/usr/bin/env python3
"""Упаковка готовых отчётов в один архив с понятными русскими именами файлов.

  python tools/package_reports.py <out.zip>
"""

import json
import os
import re
import sys
import zipfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def main():
    out = sys.argv[1]
    entries = []
    for folder in sorted(os.listdir(os.path.join(REPO, "labs"))):
        rep = os.path.join(REPO, "labs", folder, "report", "report.json")
        if not os.path.exists(rep):
            continue
        spec = json.load(open(rep, encoding="utf-8"))
        lab = spec["lab_id"]
        title = " ".join(spec.get("title_ru_lines", [])).strip()
        title = re.sub(r'[\\/:*?"<>|]', "", title)
        base = "Лаб {} - {} - Азаматов А.А".format(lab, title)
        for ext in ("pdf", "docx"):
            src = os.path.join(REPO, "reports", "lab-{}.{}".format(lab, ext))
            if os.path.exists(src):
                entries.append((src, "{}/{}.{}".format(ext.upper(), base, ext)))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for src, name in entries:
            z.write(src, name)
    print("written", out, len(entries), "files")


if __name__ == "__main__":
    main()
