#!/usr/bin/env python3
"""Отрисовка фрагмента реального протокола терминальной сессии в PNG.

Текст берётся из протоколов labrun (outputs/steps/*.txt) без изменений: картинка
лишь показывает его так, как он выглядел в окне терминала. Строки длиннее
--cols переносятся, как это сделал бы терминал такой ширины.
"""

import argparse
import os
import re
import textwrap

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "C:/Windows/Fonts/consola.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]
BOLD_CANDIDATES = [
    "C:/Windows/Fonts/consolab.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
]
# Запасные шрифты для символов, которых нет в основном (★ у Newman, ⠋ у индикаторов, иероглифы в названиях улиц)
FALLBACK_CANDIDATES = [
    "C:/Windows/Fonts/CascadiaMono.ttf",
    "C:/Windows/Fonts/seguisym.ttf",
    "C:/Windows/Fonts/msyh.ttc",
]

BG = (30, 33, 39)
TITLE_BG = (52, 56, 64)
TITLE_FG = (210, 214, 220)
FG = (221, 224, 228)
GREEN = (138, 226, 52)
BLUE = (114, 159, 207)
YELLOW = (229, 192, 123)
DIM = (150, 155, 165)

PROMPT_RE = re.compile(r"^(\([\w.-]+\) )?([\w.-]+@[\w.-]+)(:)([^$#]*)([$#] ?)(.*)$")
ROUTER_RE = re.compile(r"^([\w.-]+(?:\([\w-]+\))?#)(.*)$")


def load_font(cands, size):
    for c in cands:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


_CMAPS = {}


def has_glyph(path, ch):
    """Есть ли в шрифте глиф для символа (по таблице cmap)."""
    if path not in _CMAPS:
        try:
            from fontTools.ttLib import TTFont
            _CMAPS[path] = set(TTFont(path, fontNumber=0).getBestCmap().keys())
        except Exception:
            _CMAPS[path] = None
    cmap = _CMAPS[path]
    return True if cmap is None else ord(ch) in cmap


def first_existing(cands):
    for c in cands:
        if os.path.exists(c):
            return c
    return None


def draw_text(d, x, y, text, font, font_path, fallbacks, fill):
    """Рисует строку, подставляя запасной шрифт для отсутствующих символов. Возвращает новую x."""
    run, run_font = "", font
    for ch in text:
        f = font
        if font_path and ord(ch) > 127 and not has_glyph(font_path, ch):
            for fp, ff in fallbacks:
                if has_glyph(fp, ch):
                    f = ff
                    break
        if f is not run_font and run:
            d.text((x, y), run, font=run_font, fill=fill)
            x += d.textlength(run, font=run_font)
            run = ""
        run_font = f
        run += ch
    if run:
        d.text((x, y), run, font=run_font, fill=fill)
        x += d.textlength(run, font=run_font)
    return x


def wrap(lines, cols):
    out = []
    for line in lines:
        line = line.replace("\t", "    ")
        if len(line) <= cols:
            out.append(line)
        else:
            for i in range(0, len(line), cols):
                out.append(line[i:i + cols])
    return out


def render(text, title, out_png, cols=100, size=26, max_lines=None):
    lines = text.rstrip("\n").split("\n")
    lines = wrap(lines, cols)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
    font = load_font(FONT_CANDIDATES, size)
    bold = load_font(BOLD_CANDIDATES, size)
    font_path = first_existing(FONT_CANDIDATES)
    bold_path = first_existing(BOLD_CANDIDATES)
    fallbacks = [(p, ImageFont.truetype(p, size)) for p in FALLBACK_CANDIDATES if os.path.exists(p)]
    cw = font.getbbox("M")[2]
    lh = int(size * 1.32)
    pad = int(size * 0.8)
    title_h = int(size * 1.6)
    width = max(cols, max((len(l) for l in lines), default=10)) * cw + 2 * pad
    width = cols * cw + 2 * pad
    height = title_h + 2 * pad + lh * len(lines)
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, width, title_h], fill=TITLE_BG)
    tf = load_font(FONT_CANDIDATES, int(size * 0.85))
    tw = d.textlength(title, font=tf)
    d.text(((width - tw) / 2, (title_h - size * 0.85) / 2 - 2), title, font=tf, fill=TITLE_FG)

    y = title_h + pad
    for line in lines:
        x = pad
        m = PROMPT_RE.match(line)
        r = ROUTER_RE.match(line) if not m else None
        if m:
            venv, userhost, colon, path, sign, rest = m.groups()
            for txt, fnt, fp, col in ((venv or "", font, font_path, FG), (userhost, bold, bold_path, GREEN),
                                      (colon, font, font_path, FG), (path, bold, bold_path, BLUE),
                                      (sign, font, font_path, FG), (rest, font, font_path, FG)):
                if txt:
                    x = draw_text(d, x, y, txt, fnt, fp, fallbacks, col)
        elif r:
            x = draw_text(d, x, y, r.group(1), bold, bold_path, fallbacks, YELLOW)
            draw_text(d, x, y, r.group(2), font, font_path, fallbacks, FG)
        else:
            draw_text(d, x, y, line, font, font_path, fallbacks, FG)
        y += lh
    img.save(out_png, optimize=True)
    return img.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--title", default="Terminal")
    ap.add_argument("--cols", type=int, default=100)
    ap.add_argument("--lines", default=None, help="диапазон строк, например 1-40")
    args = ap.parse_args()
    text = open(args.src, encoding="utf-8").read()
    if args.lines:
        a, b = args.lines.split("-")
        text = "\n".join(text.split("\n")[int(a) - 1:int(b)])
    print(render(text, args.title, args.out, cols=args.cols))


if __name__ == "__main__":
    main()
