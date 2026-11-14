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
            for txt, fnt, col in ((venv or "", font, FG), (userhost, bold, GREEN), (colon, font, FG),
                                  (path, bold, BLUE), (sign, font, FG), (rest, font, FG)):
                if txt:
                    d.text((x, y), txt, font=fnt, fill=col)
                    x += d.textlength(txt, font=fnt)
        elif r:
            d.text((x, y), r.group(1), font=bold, fill=YELLOW)
            x += d.textlength(r.group(1), font=bold)
            d.text((x, y), r.group(2), font=font, fill=FG)
        else:
            d.text((x, y), line, font=font, fill=FG)
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
