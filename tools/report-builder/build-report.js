// Сборка отчёта по лабораторной работе в формате DOCX (docx-js).
// Оформление: титульный лист КГТУ (по образцу отчёта по практике), ГОСТ 7.32-2017:
// A4, поля 30/15/20/20 мм, Times New Roman 14, межстрочный 1,5, абзацный отступ 1,25 см.
//
// Использование: node build-report.js <report.resolved.json> <out.docx>

"use strict";
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, Footer,
  AlignmentType, LevelFormat, LevelSuffix, BorderStyle, ShadingType, WidthType, PageNumber,
  HeadingLevel, UnderlineType, TableLayoutType, VerticalAlign, PageBreak, NoBreakHyphen,
} = require("docx");

const FONT = "Times New Roman";
const MONO = "Courier New";
const PT = (n) => n * 2; // half-points
const TEXT_WIDTH = 9354; // 210 - 30 - 15 мм = 165 мм в twips
const LINE_15 = 360;
const INDENT = 709; // 1,25 см

const specPath = process.argv[2];
const outPath = process.argv[3];
const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));
const baseDir = path.dirname(specPath);
const cfg = JSON.parse(fs.readFileSync(path.join(__dirname, "config.json"), "utf8"));

// ---------- нумерация объектов ----------
const counters = { fig: 0, tab: 0, lst: 0 };
const labels = {};
let appendixLetter = null;
const appCounters = { fig: 0, tab: 0, lst: 0 };

function preassign(blocks) {
  let app = null;
  const c = { fig: 0, tab: 0, lst: 0 };
  const ac = { fig: 0, tab: 0, lst: 0 };
  for (const b of blocks) {
    if (b.t === "appendix") { app = b.letter; ac.fig = ac.tab = ac.lst = 0; continue; }
    const kind = b.t === "figure" ? "fig" : b.t === "table" ? "tab" : b.t === "listing" ? "lst" : null;
    if (!kind) continue;
    let num;
    if (app) { ac[kind] += 1; num = `${app}.${ac[kind]}`; } else { c[kind] += 1; num = String(c[kind]); }
    if (b.id) labels[`${kind}:${b.id}`] = num;
    b._num = num;
  }
}

// ---------- inline-разметка: **жирный**, `код`, {fig:id} ----------
function resolveRefs(text) {
  return text.replace(/\{(fig|tab|lst):([\w.-]+)\}/g, (m, k, id) => {
    const v = labels[`${k}:${id}`];
    if (!v) { console.error(`WARN: unresolved reference ${m}`); return "??"; }
    return v;
  });
}

// Неразрывные пробелы по правилам русской типографики: ссылка [N] не отрывается от слова,
// «рисунок 5», «часть 2», «15 с», «5,7 МБ», «Р. Филдинг» не разрываются, строка не начинается с тире.
const NBSP = " ";
function typo(text) {
  return text
    .replace(/(\S) +\[(?=\d)/g, `$1${NBSP}[`)
    .replace(/(^|[^\wА-Яа-яЁё])((?:[Рр]исун|[Тт]абли|[Лл]истинг|[Пп]риложени|[Чч]аст|[Шш]аг|[Рр]аздел|[Пп]одраздел|[Пп]ункт)[а-яё]*) (?=\d|[А-ЯЁ](?![а-яё]))/g, `$1$2${NBSP}`)
    .replace(/(\d) (?=(?:с|мс|мкс|мин|ч|Б|байт[а-яё]*|КБ|кБ|МБ|ГБ|КиБ|МиБ|ГиБ|км|м|мм|см|пт|%)(?=$|[\s.,;:)»]))/g, `$1${NBSP}`)
    .replace(/№ (?=\d)/g, `№${NBSP}`)
    .replace(/(^|[\s(«])([А-ЯЁ]\.) (?=[А-ЯЁ][а-яё])/g, `$1$2${NBSP}`)
    .replace(/ (—|–) /g, `${NBSP}$1 `);
}

// Код внутри строки: дефис неразрывный, чтобы Word не переносил команды и пути по дефису
// («lab-env/setup-» / «labvm.sh», «ключом -» / «-hostname»). Длинные токены переносить можно.
function codeChildren(text) {
  if (text.length > 40 || !text.includes("-")) return [text];
  const parts = text.split("-");
  const out = [];
  parts.forEach((p, i) => {
    if (i) out.push(new NoBreakHyphen());
    if (p) out.push(p);
  });
  return out;
}

// Строка листинга: неразрывные дефисы внутри отдельных слов, перенос возможен по пробелам.
function codeLineChildren(line) {
  const out = [];
  for (const tok of line.split(/( +)/)) {
    if (!tok) continue;
    for (const c of codeChildren(tok)) {
      if (typeof c === "string" && typeof out[out.length - 1] === "string") out[out.length - 1] += c;
      else out.push(c);
    }
  }
  return out;
}

function runs(text, base = {}) {
  text = resolveRefs(text);
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: typo(text.slice(last, m.index)), ...base }));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(new TextRun({ text: typo(tok.slice(2, -2)), bold: true, ...base }));
    else out.push(new TextRun({ children: codeChildren(tok.slice(1, -1)), font: MONO, size: base.size ? base.size - 2 : PT(12), ...base, ...(base.font ? {} : { font: MONO }) }));
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(new TextRun({ text: typo(text.slice(last)), ...base }));
  return out;
}

// ---------- базовые абзацы ----------
const P = (text, opts = {}) => new Paragraph({ children: runs(text, opts.run || {}), ...opts.para });

function body(text) {
  return new Paragraph({ children: runs(text), alignment: AlignmentType.JUSTIFIED });
}

function labelPara(label, text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    children: [new TextRun({ text: label + " ", bold: true }), ...runs(text)],
  });
}

let h1n = 0;
let h2n = 0;
let h3n = 0;
function heading(level, text, numbered = true, pageBreak = false) {
  let prefix = "";
  if (numbered && !appendixLetter) {
    if (level === 1) { h1n += 1; h2n = 0; h3n = 0; prefix = `${h1n} `; }
    else if (level === 2) { h2n += 1; h3n = 0; prefix = `${h1n}.${h2n} `; }
    else { h3n += 1; prefix = `${h1n}.${h2n}.${h3n} `; }
  }
  const hl = level === 1 ? HeadingLevel.HEADING_1 : level === 2 ? HeadingLevel.HEADING_2 : HeadingLevel.HEADING_3;
  return new Paragraph({
    heading: hl,
    pageBreakBefore: pageBreak,
    children: [new TextRun({ text: prefix + text })],
  });
}

function caption(text, align) {
  return new Paragraph({
    alignment: align,
    indent: { firstLine: 0 },
    spacing: { before: align === AlignmentType.CENTER ? 0 : 120, after: align === AlignmentType.CENTER ? 200 : 60, line: LINE_15 },
    keepNext: align !== AlignmentType.CENTER,
    children: runs(text),
  });
}

function imageSize(file) {
  const buf = fs.readFileSync(file);
  // PNG: ширина и высота в IHDR
  if (buf.readUInt32BE(0) === 0x89504e47) return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20), buf, type: "png" };
  // JPEG: ищем SOF0/SOF2
  let i = 2;
  while (i < buf.length) {
    const marker = buf.readUInt16BE(i);
    const len = buf.readUInt16BE(i + 2);
    if (marker === 0xffc0 || marker === 0xffc2) return { h: buf.readUInt16BE(i + 5), w: buf.readUInt16BE(i + 7), buf, type: "jpg" };
    i += 2 + len;
  }
  throw new Error("unknown image " + file);
}

function figure(b) {
  const file = path.resolve(baseDir, b.image);
  const { w, h, buf, type } = imageSize(file);
  const maxW = (b.width_mm || (b.terminal ? 155 : 165)) / 25.4 * 96; // px при 96 dpi
  const scale = Math.min(1, maxW / w, (b.max_height_mm || 215) / 25.4 * 96 / h);
  const width = Math.round(w * scale);
  const height = Math.round(h * scale);
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      indent: { firstLine: 0 },
      keepNext: true,
      spacing: { before: 120, after: 60, line: 240 },
      children: [new ImageRun({ type, data: buf, transformation: { width, height }, altText: { title: b.caption, description: b.caption, name: b.id || "figure" } })],
    }),
    caption(`Рисунок ${b._num} – ${b.caption}`, AlignmentType.CENTER),
  ];
}

function listing(b) {
  const out = [caption(`Листинг ${b._num} – ${b.caption}`, AlignmentType.LEFT)];
  const lines = String(b.code).replace(/\t/g, "    ").replace(/\s+$/, "").split("\n");
  const size = PT(b.font_size || 10);
  const charW = Math.round((b.font_size || 10) * 0.6 * 20); // ширина символа Courier New в twips
  const border = { style: BorderStyle.SINGLE, size: 4, color: "8C8C8C", space: 3 };
  lines.forEach((line, i) => {
    out.push(new Paragraph({
      alignment: AlignmentType.LEFT,
      // перенесённая часть длинной строки сдвинута на два символа, чтобы её не путали с новой строкой
      indent: { firstLine: 0, left: 57 + 2 * charW, hanging: 2 * charW, right: 57 },
      spacing: { before: 0, after: i === lines.length - 1 ? 160 : 0, line: 240 },
      keepLines: true,
      keepNext: lines.length <= 25 && i < lines.length - 1,
      border: { top: border, bottom: border, left: border, right: border },
      shading: { type: ShadingType.CLEAR, fill: "F4F4F4", color: "auto" },
      // знак абзаца того же размера, что текст: иначе пустые строки листинга выше остальных
      run: { font: MONO, size },
      children: [new TextRun({ children: line.length ? codeLineChildren(line) : [" "], font: MONO, size })],
    }));
  });
  return out;
}

function cellPara(text, opts = {}) {
  return new Paragraph({
    alignment: opts.align || AlignmentType.LEFT,
    indent: { firstLine: 0 },
    spacing: { before: 20, after: 20, line: 240 },
    children: runs(String(text), { size: PT(opts.size || 12), bold: !!opts.bold }),
  });
}

function table(b) {
  const out = [caption(`Таблица ${b._num} – ${b.caption}`, AlignmentType.LEFT)];
  const ncol = b.header.length;
  const ratios = b.widths || Array(ncol).fill(1);
  const sum = ratios.reduce((a, c) => a + c, 0);
  const widths = ratios.map((r) => Math.floor((r / sum) * TEXT_WIDTH));
  widths[widths.length - 1] += TEXT_WIDTH - widths.reduce((a, c) => a + c, 0);
  const border = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
  const borders = { top: border, bottom: border, left: border, right: border };
  const mk = (cells, isHeader) => new TableRow({
    tableHeader: isHeader,
    cantSplit: true,
    children: cells.map((c, i) => new TableCell({
      width: { size: widths[i], type: WidthType.DXA },
      borders,
      verticalAlign: VerticalAlign.CENTER,
      margins: { top: 40, bottom: 40, left: 80, right: 80 },
      children: String(c).split("\n").map((line) => cellPara(line, { bold: isHeader, align: isHeader ? AlignmentType.CENTER : AlignmentType.LEFT, size: b.font_size || 12 })),
    })),
  });
  // ГОСТ 7.32-2017, 6.6.6: над перенесённой частью таблицы пишут «Продолжение таблицы N».
  // Номера строк, с которых начинается новая страница, проставляет fit_layout.py (split_at).
  const cuts = [...new Set((b.split_at || []).filter((r) => r > 0 && r < b.rows.length))].sort((x, y) => x - y);
  const bounds = [0, ...cuts, b.rows.length];
  for (let k = 0; k + 1 < bounds.length; k++) {
    if (k > 0) {
      out.push(new Paragraph({
        alignment: AlignmentType.LEFT,
        indent: { firstLine: 0 },
        pageBreakBefore: true,
        keepNext: true,
        spacing: { before: 0, after: 60, line: LINE_15 },
        children: [new TextRun({ text: `Продолжение таблицы ${b._num}` })],
      }));
    }
    out.push(new Table({
      width: { size: TEXT_WIDTH, type: WidthType.DXA },
      columnWidths: widths,
      layout: TableLayoutType.FIXED,
      rows: [mk(b.header, true), ...b.rows.slice(bounds[k], bounds[k + 1]).map((r) => mk(r, false))],
    }));
  }
  out.push(new Paragraph({ children: [], spacing: { after: 120 } }));
  return out;
}

function list(items, ref) {
  return items.map((it, i) => new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    numbering: { reference: ref, level: 0 },
    children: runs(it + (ref === "dash" ? (i === items.length - 1 ? "." : ";") : "")),
  }));
}

function plainList(items, ref, align = AlignmentType.JUSTIFIED) {
  return items.map((it) => new Paragraph({ alignment: align, numbering: { reference: ref, level: 0 }, children: runs(it) }));
}

// ---------- титульный лист ----------
function titlePage() {
  const c = (text, o = {}) => new Paragraph({
    alignment: AlignmentType.CENTER,
    indent: { firstLine: 0 },
    spacing: { line: o.line || 240, after: o.after || 0, before: o.before || 0 },
    children: [new TextRun({ text, bold: o.bold, size: o.size, underline: o.underline ? { type: UnderlineType.SINGLE } : undefined })],
  });
  const empty = (n) => Array.from({ length: n }, () => new Paragraph({ indent: { firstLine: 0 }, spacing: { line: 240 }, children: [] }));
  const signer = (label, value, after = 120) => new Paragraph({
    alignment: AlignmentType.LEFT,
    indent: { firstLine: 0, left: 720 },
    spacing: { line: 360, after },
    children: [new TextRun({ text: label + " ", bold: true }), new TextRun({ text: value, underline: { type: UnderlineType.SINGLE } })],
  });
  return [
    c(cfg.ministry, { bold: true }),
    c(cfg.university, { bold: true, after: 120 }),
    c(cfg.institute, { bold: true }),
    c(cfg.department, { bold: true }),
    ...empty(7),
    c("ОТЧЕТ", { bold: true, size: PT(18), line: 360 }),
    c(`по лабораторной работе № ${spec.lab_id}`, { line: 360 }),
    c(`по дисциплине «${cfg.discipline}»`, { line: 360, after: 200 }),
    c("Тема:", { underline: true, line: 360 }),
    ...spec.title_ru_lines.map((l) => c(l, { bold: true, line: 360 })),
    ...empty(spec.title_ru_lines.length > 2 ? 7 : 9),
    signer("Выполнил:", cfg.student),
    signer("Проверил:", cfg.teacher || " ".repeat(38), 0),
    ...empty(5),
    c(cfg.city_year, { bold: true }),
    new Paragraph({ children: [new PageBreak()] }),
  ];
}

// ---------- основная часть ----------
function render(blocks) {
  const out = [];
  for (const b of blocks) {
    switch (b.t) {
      case "h1": out.push(heading(1, b.text, b.num !== false, !!b.newpage)); break;
      case "h2": out.push(heading(2, b.text, b.num !== false)); break;
      case "h3": out.push(heading(3, b.text, b.num !== false)); break;
      case "p": out.push(body(b.text)); break;
      case "label": out.push(labelPara(b.label, b.text)); break;
      case "bullets": out.push(...list(b.items, "dash")); break;
      case "numbered": out.push(...plainList(b.items, b.style === "dot" ? "num-dot" : "num-paren")); break;
      case "figure": out.push(...figure(b)); break;
      case "listing": out.push(...listing(b)); break;
      case "table": out.push(...table(b)); break;
      case "note": out.push(new Paragraph({ alignment: AlignmentType.JUSTIFIED, children: [new TextRun({ text: "Примечание – " }), ...runs(b.text)] })); break;
      case "pagebreak": out.push(new Paragraph({ children: [new PageBreak()] })); break;
      case "sources":
        out.push(heading(1, "Список использованных источников", false, !!b.newpage));
        out.push(...plainList(b.items, "num-dot", AlignmentType.LEFT));
        break;
      case "appendix":
        appendixLetter = b.letter;
        out.push(new Paragraph({ pageBreakBefore: true, alignment: AlignmentType.CENTER, indent: { firstLine: 0 }, spacing: { line: LINE_15 }, children: [new TextRun({ text: `ПРИЛОЖЕНИЕ ${b.letter}`, bold: true })] }));
        out.push(new Paragraph({ alignment: AlignmentType.CENTER, indent: { firstLine: 0 }, spacing: { line: LINE_15, after: 240 }, children: [new TextRun({ text: b.title, bold: true })] }));
        break;
      default:
        throw new Error("unknown block type " + b.t);
    }
  }
  return out;
}

preassign(spec.blocks);
const children = [...titlePage(), ...render(spec.blocks)];

const headingStyle = (id, name, outline) => ({
  id, name, basedOn: "Normal", next: "Normal", quickFormat: true,
  run: { font: FONT, size: PT(14), bold: true, color: "000000" },
  paragraph: { alignment: AlignmentType.LEFT, spacing: { before: outline === 0 ? 240 : 160, after: 120, line: LINE_15 }, indent: { firstLine: 0 }, keepNext: true, keepLines: true, outlineLevel: outline },
});

const doc = new Document({
  creator: cfg.author_meta,
  lastModifiedBy: cfg.author_meta,
  title: `Лабораторная работа ${spec.lab_id}`,
  description: spec.title_ru_lines.join(" "),
  styles: {
    default: {
      document: {
        run: { font: FONT, size: PT(14), language: { value: "ru-RU" } },
        paragraph: { spacing: { line: LINE_15, before: 0, after: 0 }, indent: { firstLine: INDENT } },
      },
    },
    paragraphStyles: [
      headingStyle("Heading1", "Heading 1", 0),
      headingStyle("Heading2", "Heading 2", 1),
      headingStyle("Heading3", "Heading 3", 2),
    ],
  },
  numbering: {
    config: [
      {
        reference: "dash",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, suffix: LevelSuffix.SPACE,
          style: { paragraph: { indent: { left: 0, firstLine: INDENT } }, run: { font: FONT } } }],
      },
      {
        reference: "num-paren",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1)", alignment: AlignmentType.LEFT, suffix: LevelSuffix.SPACE,
          style: { paragraph: { indent: { left: 0, firstLine: INDENT } } } }],
      },
      {
        reference: "num-dot",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, suffix: LevelSuffix.SPACE,
          style: { paragraph: { indent: { left: 0, firstLine: INDENT } } } }],
      },
    ],
  },
  sections: [{
    properties: {
      titlePage: true,
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1134, bottom: 1134, left: 1701, right: 851, header: 709, footer: 567 },
      },
    },
    footers: {
      default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, indent: { firstLine: 0 }, children: [new TextRun({ children: [PageNumber.CURRENT], size: PT(12) })] })] }),
      first: new Footer({ children: [new Paragraph({ children: [] })] }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(outPath, buf);
  console.log(`OK ${outPath} (${(buf.length / 1024).toFixed(0)} KB)`);
});
