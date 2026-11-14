#!/usr/bin/env python3
"""Копирует протоколы последнего успешного прогона CI в labs/<lab>/outputs/.

  python tools/import_outputs.py 14-7.4.7-ansible-backup-config [ещё папки...]
  python tools/import_outputs.py --all

Рядом с протоколами создаётся RUN.md со ссылкой на прогон GitHub Actions,
чтобы любой мог открыть исходный журнал выполнения.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Закрытые ключи, созданные на стенде во время работы (например, ключ TLS веб-сервера в 5.5),
# остаются только в артефакте прогона и в репозиторий не копируются.
PRIVATE_KEYS = ("*.key", "*.pem", "id_rsa*", "id_ecdsa*", "id_ed25519*", "*.p12", "*.pfx")
GH = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"
SLUG = "medivhkr/devsecops-labs"


def gh(*args):
    return subprocess.check_output([GH, *args], universal_newlines=True, encoding="utf-8")


def lab_id(folder):
    return re.match(r"\d+-([\d.]+)-", folder).group(1)


def import_lab(folder, run_id=None, variant=None):
    wid = "lab-{}{}.yml".format(lab_id(folder), "-" + variant if variant else "")
    if run_id is None:
        runs = json.loads(gh("run", "list", "-R", SLUG, "--workflow", wid, "--branch", "main", "--status", "success",
                             "--limit", "1", "--json", "databaseId,headSha,createdAt,url"))
        if not runs:
            print("no successful run for", folder)
            return False
        run = runs[0]
    else:
        run = json.loads(gh("run", "view", str(run_id), "-R", SLUG, "--json", "databaseId,headSha,createdAt,url,conclusion"))
    tmp = tempfile.mkdtemp()
    gh("run", "download", str(run["databaseId"]), "-R", SLUG, "-D", tmp)
    src = os.path.join(tmp, folder + ("-" + variant if variant else ""))
    if not os.path.isdir(src):
        src = os.path.join(tmp, os.listdir(tmp)[0])
    dst = os.path.join(REPO, "labs", folder, "outputs" + ("-" + variant if variant else ""))
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("raw.log", *PRIVATE_KEYS))
    with open(os.path.join(dst, "RUN.md"), "w", encoding="utf-8") as fh:
        fh.write("# Протокол выполнения\n\n")
        fh.write("Файлы в этом каталоге получены при реальном выполнении сценария `scenario{}.yml` в GitHub Actions.\n\n"
                 .format("-" + variant if variant else ""))
        fh.write("- Прогон: {}\n".format(run["url"]))
        fh.write("- Коммит: `{}`\n".format(run["headSha"]))
        fh.write("- Дата запуска (UTC): {}\n".format(run["createdAt"]))
        fh.write("\n`transcript.txt` содержит сессию терминала целиком, `steps/` - вывод по шагам, `files/` - файлы, созданные в работе.\n")
    shutil.rmtree(tmp, ignore_errors=True)
    print("imported", folder, "from run", run["databaseId"])
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--run", type=int, default=None)
    ap.add_argument("--variant", default=None, help="например osm: workflow lab-<id>-osm.yml, каталог outputs-osm")
    args = ap.parse_args()
    folders = sorted(os.listdir(os.path.join(REPO, "labs"))) if args.all else args.folders
    ok = all(import_lab(f, args.run, args.variant) for f in folders)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
