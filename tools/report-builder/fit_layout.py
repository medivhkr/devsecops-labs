#!/usr/bin/env python3
"""Подгонка вёрстки: пустые места перед рисунками и переносы таблиц.

Когда рисунок вместе с подписью не помещается в остаток страницы, Word переносит
его на следующую, и внизу остаётся пустое место. ГОСТ 7.32 разрешает размещать
рисунок «на следующей странице» после ссылки на него, поэтому скрипт делает то же,
что сделал бы человек в Word:

  1. если рисунку не хватает совсем немного места, слегка уменьшает его (не меньше 80 %);
  2. иначе поднимает перед рисунком следующие за ним абзацы текста, и они заполняют
     страницу, а рисунок открывает следующую;
  3. если ни то ни другое невозможно (за рисунком сразу заголовок), разрыв остаётся.

Кроме того, если таблица не поместилась на страницу и Word перенёс её часть,
скрипт отмечает строку переноса (split_at), и над перенесённой частью появляется
надпись «Продолжение таблицы N» (ГОСТ 7.32-2017, 6.6.6).

Скрипт собирает PDF, находит первый по порядку дефект, правит report.json и повторяет.
Запускать после всех правок текста: любая правка сдвигает страницы.

  python tools/report-builder/fit_layout.py labs/<папка> [labs/<папка> ...]
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys

import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PT2MM = 25.4 / 72
MARGIN_PT = 1134 / 20            # поля сверху и снизу 2 см (в пунктах)
GAP_SHARE = 0.33                 # разрыв больше трети страницы считается дефектом
MIN_SCALE = 0.80                 # мельче рисунок терминала становится трудно читать
MOVABLE = {"p", "bullets", "numbered", "note"}
NO_MOVE_RE = re.compile(r"\b(выше|ниже|следующ\w* рисун\w*)\b", re.I)


def build(lab_dir):
    r = subprocess.run([sys.executable, os.path.join(HERE, "build.py"), lab_dir], stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, universal_newlines=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or "WARN" in r.stdout:
        raise SystemExit("сборка не удалась:\n" + r.stdout[-1500:])


def content_bottom(page):
    H = page.rect.height
    ys = [b[3] for b in page.get_text("blocks") if not (b[1] > H - 60 and b[4].strip().isdigit())]
    ys += [im["bbox"][3] for im in page.get_image_info()]
    ys += [d["rect"].y1 for d in page.get_drawings() if d["rect"].y1 < H - 60]
    return max(ys) if ys else None


def find_gaps(pdf):
    """[(страница, свободно_пт, высота_рисунка_пт, ширина_рисунка_пт, высота_подписи_пт, номер_рисунка)]"""
    doc = pymupdf.open(pdf)
    gaps = []
    for i in range(1, doc.page_count - 1):
        page, nxt = doc[i], doc[i + 1]
        H = page.rect.height
        bottom = H - MARGIN_PT
        cb = content_bottom(page)
        if cb is None:
            continue
        free = bottom - cb
        if free / (bottom - MARGIN_PT) <= GAP_SHARE:
            continue
        imgs = sorted(nxt.get_image_info(), key=lambda im: im["bbox"][1])
        if not imgs:
            continue
        im = imgs[0]["bbox"]
        if any(b[3] <= im[1] + 1 for b in nxt.get_text("blocks")):
            continue  # над рисунком есть текст: страница начинается не с рисунка
        # подпись: первый текстовый блок, который заканчивается ниже рисунка
        # (Word иногда включает в него пустую строку абзаца с рисунком)
        cap = sorted((b for b in nxt.get_text("blocks") if b[3] > im[3] and b[6] == 0), key=lambda b: b[1])
        if not cap:
            continue
        m = re.match(r"Рисунок (\d+) –", cap[0][4].strip())
        if not m:
            continue  # рисунок приложения (А.1) или не рисунок
        gaps.append((i + 1, free, im[3] - im[1], im[2] - im[0], cap[0][3] - im[3], int(m.group(1))))
    return gaps


def plain(text):
    return re.sub(r"\*\*|`|\{(fig|tab|lst):[\w.-]+\}", "", text)


def est_height_pt(b):
    """Грубая оценка высоты блока текста: ~70 знаков в строке, 1,5 интервала при 14 пт."""
    texts = [b.get("text", "")] if b["t"] in ("p", "note") else list(b.get("items", []))
    lines = sum(max(1, math.ceil((len(plain(t if isinstance(t, str) else json.dumps(t))) + 6) / 70)) for t in texts)
    return lines * 24.2


def caption_height_pt(num, caption):
    """Высота подписи по её длине: ~68 знаков в строке, 1,5 интервала, 10 пт после абзаца."""
    n = len("Рисунок {} – ".format(num)) + len(plain(caption))
    return math.ceil(n / 68) * 24.2 + 10


def apply_fix(spec, gap, log, state):
    """state[номер рисунка] = исходная ширина в мм: рисунок только уменьшается, не ниже MIN_SCALE."""
    page, free, fig_h, fig_w, _, num = gap
    blocks = spec["blocks"]
    first_app = next((i for i, b in enumerate(blocks) if b["t"] == "appendix"), len(blocks))
    figs = [i for i, b in enumerate(blocks[:first_app]) if b["t"] in ("figure", "terminal")]
    k = figs[num - 1]
    fb = blocks[k]
    w_mm = fig_w * PT2MM
    orig = state.setdefault(num, w_mm)
    need = (free - 9 - caption_height_pt(num, fb.get("caption", "")) - 6) / fig_h
    tag = "рисунок {} (стр. {}, свободно {:.0f} мм)".format(num, page, free * PT2MM)

    def shrink():
        # по расчёту рисунок уже должен помещаться: уменьшаем шагами по 3 %, пока Word не поставит его
        new = w_mm * min(need, 0.97)
        if new < orig * MIN_SCALE:
            return False
        fb["width_mm"] = round(new, 1)
        log.append("{}: уменьшен до {:.0f} % исходной ширины".format(tag, 100 * new / orig))
        return True

    if need >= 0.9 and shrink():
        return True
    moved, h = [], 0.0
    j = k + 1
    while j < len(blocks) and blocks[j]["t"] in MOVABLE and h < free - 20:
        txt = blocks[j].get("text", "") + " ".join(map(str, blocks[j].get("items", [])))
        if NO_MOVE_RE.search(txt):
            break
        h += est_height_pt(blocks[j])
        moved.append(j)
        j += 1
    if moved:
        chunk = [blocks[x] for x in moved]
        del blocks[moved[0]:moved[-1] + 1]
        blocks[k:k] = chunk
        first = plain(chunk[0].get("text", "") or str(chunk[0].get("items", [""])[0]))[:70]
        log.append("{}: перед рисунком поднято блоков текста: {} («{}…»)".format(tag, len(chunk), first))
        return True
    if shrink():
        return True
    log.append("{}: оставлен (за рисунком заголовок, уменьшать сильнее нельзя)".format(tag))
    return False


def norm(text):
    """Текст ячейки без разметки и пробелов: так его можно сравнить с текстом из PDF."""
    return re.sub(r"\s+", "", plain(text).replace("\u00a0", " ")).replace("\u2011", "-")


def find_table_splits(pdf):
    """Страницы, которые начинаются с продолжения таблицы без надписи «Продолжение таблицы N».

    Word переносит таблицу сам и повторяет её шапку (tableHeader). Возвращает
    [(страница, номер_таблицы, текст первой ячейки первой перенесённой строки)].
    """
    doc = pymupdf.open(pdf)
    out = []
    last_tab = None
    for i, page in enumerate(doc):
        if i > 0 and last_tab is not None:
            hlines = sorted(d["rect"].y0 for d in page.get_drawings()
                            if d["rect"].height < 2 and d["rect"].width > 100)
            spans = []
            for b in page.get_text("dict")["blocks"]:
                for l in b.get("lines", []):
                    for s in l["spans"]:
                        if s["text"].strip():
                            spans.append(s)
            top = min((s["bbox"][1] for s in spans), default=None)
            starts_with_table = (hlines and top is not None and hlines[0] < MARGIN_PT + 8 and hlines[0] <= top)
            if starts_with_table:
                first = [s for s in spans if s["bbox"][1] < top + 4]
                if not any("Продолжение таблицы" in s["text"] for s in first):
                    # строка шапки ограничена первыми двумя линиями, первая строка данных - второй и третьей
                    rows = [y for k, y in enumerate(hlines) if k == 0 or y - hlines[k - 1] > 3]
                    if len(rows) >= 3:
                        y0, y1 = rows[1], rows[2]
                        vx = sorted({round(d["rect"].x0) for d in page.get_drawings()
                                     if d["rect"].width < 2 and d["rect"].height > 5
                                     and d["rect"].y0 < y1 and d["rect"].y1 > y0})
                        if len(vx) >= 2:
                            cell = [s for s in spans if y0 < (s["bbox"][1] + s["bbox"][3]) / 2 < y1
                                    and vx[0] <= s["bbox"][0] < vx[1]]
                            cell.sort(key=lambda s: (round(s["bbox"][1]), s["bbox"][0]))
                            out.append((i + 1, last_tab, "".join(s["text"] for s in cell)))
        for m in re.finditer(r"^Таблица (\d+) –", page.get_text(), re.M):
            last_tab = int(m.group(1))
    return out


def apply_table_split(spec, split, log):
    page, num, first_cell = split
    blocks = spec["blocks"]
    first_app = next((i for i, b in enumerate(blocks) if b["t"] == "appendix"), len(blocks))
    tabs = [b for b in blocks[:first_app] if b["t"] == "table"]
    if num > len(tabs):
        return False
    tb = tabs[num - 1]
    done = max(tb.get("split_at", []) or [0])
    want = norm(first_cell)
    for r in range(done + 1, len(tb["rows"])):
        if want and norm(str(tb["rows"][r][0]).replace("\n", " ")) == want:
            tb.setdefault("split_at", []).append(r)
            log.append("таблица {} (стр. {}): перенос перед строкой {} с надписью «Продолжение таблицы {}»".format(
                num, page, r + 1, num))
            return True
    log.append("таблица {} (стр. {}): строку «{}» найти не удалось, надпись не добавлена".format(num, page, first_cell[:40]))
    return False


def fit(lab_dir, max_iter=30):
    """Исправляет дефекты по порядку страниц: правка на странице N меняет только страницы после N."""
    path = os.path.join(lab_dir, "report", "report.json")
    spec = json.load(open(path, encoding="utf-8"))
    for b in spec["blocks"]:
        b.pop("split_at", None)  # места переноса таблиц определяются заново при каждом запуске
    save(path, spec)
    log, skip, state = [], set(), {}
    for _ in range(max_iter):
        build(lab_dir)
        spec = json.load(open(path, encoding="utf-8"))
        pdf = os.path.join(REPO, "reports", "lab-{}.pdf".format(spec["lab_id"]))
        defects = [(g[0], "fig", g) for g in find_gaps(pdf) if ("fig", g[5]) not in skip]
        defects += [(t[0], "tab", t) for t in find_table_splits(pdf) if ("tab", t[1], t[0]) not in skip]
        if not defects:
            break
        page, kind, d = min(defects, key=lambda x: (x[0], x[1]))
        ok = apply_fix(spec, d, log, state) if kind == "fig" else apply_table_split(spec, d, log)
        if ok:
            save(path, spec)
        else:
            skip.add(("fig", d[5]) if kind == "fig" else ("tab", d[1], d[0]))
    return spec["lab_id"], log


def save(path, spec):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)
        f.write("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lab_dirs", nargs="+")
    args = ap.parse_args()
    for d in args.lab_dirs:
        try:
            lab, log = fit(os.path.abspath(d))
        except SystemExit as exc:
            print("{}: ОШИБКА {}".format(d, exc))
            continue
        print("{}: {}".format(lab, "без изменений" if not log else ""))
        for line in log:
            print("   " + line)
        sys.stdout.flush()


if __name__ == "__main__":
    main()
