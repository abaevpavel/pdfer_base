#!/usr/bin/env python3
"""
Локальный раннер для Forge Document Builder темплейтов.

Рендерит любой темплейт из ./templates на тестовом payload'е из ./payloads,
БЕЗ Flask. Всегда пишет HTML в ./out (превью в браузере), а если в системе
есть wkhtmltopdf — дополнительно генерит PDF.

Консолидирует препроцессинг из прод-роутов (proposal.py, change_order.py,
internal_scope.py, subcontractor.py): EXP[...]EXP, priceHidden, totalFormatted,
markdown **bold**, grandTotalFormatted + Jinja-фильтры linkify и money.

Использование:
    python render.py <template> [payload]
    python render.py --all [payload]

Примеры:
    python render.py change_order_internal
    python render.py initial_contract example02.json
    python render.py --all example01.json

<template> — имя файла из ./templates с .html или без.
[payload]  — имя файла из ./payloads (по умолчанию example01.json).
"""
import sys
import os
import re
import math
import json
import datetime
import unicodedata
import subprocess
import tempfile
import time
from decimal import Decimal
from urllib.parse import urlsplit

from jinja2 import Environment, FileSystemLoader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
PAYLOADS_DIR = os.path.join(BASE_DIR, "payloads")
OUT_DIR = os.path.join(BASE_DIR, "out")

DEFAULT_PAYLOAD = "example01.json"

# Headless-браузер для флага --pdf (Chrome/Chromium бьёт на страницы и режет
# высокие строки так же, как прод-движок wkhtmltopdf — в отличие от Paged.js).
_CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
]


def _find_chrome():
    for p in _CHROME_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def render_pdf_chrome(html_path, pdf_path):
    """HTML → PDF через headless Chrome (своя пагинация, разрыв высоких строк)."""
    chrome = _find_chrome()
    if not chrome:
        print("  PDF:  пропущен (Chrome/Chromium не найден)")
        return
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
    with tempfile.TemporaryDirectory() as profile:
        cmd = [
            chrome, "--headless=new", "--disable-gpu",
            "--no-pdf-header-footer",
            "--no-sandbox",
            f"--user-data-dir={profile}",
            "--virtual-time-budget=2000",
            f"--print-to-pdf={pdf_path}",
            "file://" + os.path.abspath(html_path),
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Chrome печатает PDF быстро, но сам не выходит — поллим файл и убиваем процесс
        deadline = time.time() + 30
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                time.sleep(0.4)  # дать дописать файл
                proc.terminate()
                break
            time.sleep(0.3)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
        print(f"  PDF:  {pdf_path}  (headless Chrome)")
    else:
        print("  PDF:  не создан (Chrome не отрисовал)")


# ---------- Jinja-фильтры (как в проде) ----------

def linkify_urls(text):
    if text is None:
        return ""
    source = str(text)
    pattern = re.compile(r'(?<!["\'=])(https?://[^\s<"]+)')

    def _repl(match):
        url = match.group(1)
        trailing = ""
        while url and url[-1] in ".,);:]!?":
            trailing = url[-1] + trailing
            url = url[:-1]
        domain = urlsplit(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        if not domain:
            domain = "link"
        link_text = f"{domain} - View Link"
        return f'<a href="{url}" style="color:#0000EE; text-decoration: underline;">{link_text}</a>{trailing}'

    return pattern.sub(_repl, source)


def _only_number_like(s):
    if s is None:
        return None
    s = unicodedata.normalize("NFKC", str(s)).strip()
    s_no_sym = s.replace("$", "").replace(" ", "")
    if re.fullmatch(r"[0-9][0-9,]*([.][0-9]+)?", s_no_sym):
        try:
            return Decimal(s_no_sym.replace(",", ""))
        except Exception:
            return None
    return None


def money(val):
    if isinstance(val, (int, float, Decimal)):
        try:
            return f"${Decimal(str(val)):,.2f}"
        except Exception:
            return f"${val}"
    as_num = _only_number_like(val)
    if as_num is not None:
        return f"${as_num:,.2f}"
    return "" if val is None else str(val)


# ---------- Препроцессинг payload'а ----------

def _walk_items(categories):
    for cat in categories or []:
        for subcat in cat.get("subcategories", []) or []:
            for item in subcat.get("items", []) or []:
                yield item


def _parse_money_number(raw):
    if raw is None:
        return None
    s = str(raw).replace(",", "").replace(" ", "").replace("$", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _grand_total_value(body):
    infos = body.get("estimatesInfo") or []
    if infos:
        tc = _parse_money_number(infos[0].get("totalCost"))
        if tc is not None:
            return tc
    total = 0.0
    for cat in body.get("categories") or []:
        v = _parse_money_number(cat.get("total"))
        if v is not None:
            total += v
    return total


def process_payload(body):
    """Суперсет препроцессинга всех прод-роутов. Безвреден для любого темплейта."""
    sqFt = 0
    infos = body.get("estimatesInfo") or []
    if infos:
        sqFt = infos[0].get("squareFootage", 0)

    eval_globals = {"sqFt": sqFt, "math": math, "__builtins__": __builtins__}

    def process_expressions(text):
        if not text or "EXP[" not in text or "]EXP" not in text:
            return text
        expressions = re.findall(r"EXP\[(.*?)\]EXP", text)
        tmp = text.replace("EXP[", "").replace("]EXP", "")
        for expr in expressions:
            try:
                result = eval(expr, eval_globals)
            except Exception:
                result = expr
            tmp = tmp.replace(expr, str(result))
        return tmp

    def process_markdown(text):
        if not text:
            return text
        return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

    for cat in body.get("categories", []):
        cat["totalFormatted"] = f"{cat.get('total', 0):,}"

    for item in _walk_items(body.get("categories", [])):
        if item.get("priceHidden", False):
            item["price"] = "N/A"
            item["total"] = "N/A"

        addi = item.get("additionalInfo") or ""
        if addi:
            item["additionalInfo"] = process_expressions(addi)

        long_desc = item.get("longDescription") or ""
        if long_desc:
            item["longDescription"] = process_expressions(long_desc)

        instr = item.get("internalInstructions") or ""
        if instr:
            item["internalInstructions"] = process_markdown(process_expressions(instr))

        notes = item.get("internalNotes") or ""
        if notes:
            item["internalNotes"] = process_markdown(process_expressions(notes))

    body["grandTotalFormatted"] = f"${_grand_total_value(body):,.2f}"
    return body


# ---------- Рендер ----------

def render_one(template_name, body, paged=False, pdf=False):
    if not template_name.endswith(".html"):
        template_name += ".html"

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=False)
    env.filters["linkify"] = linkify_urls
    env.filters["money"] = money
    template = env.get_template(template_name)

    custom_items = [i for i in _walk_items(body.get("categories", []))
                    if i.get("catelogId") == "Custom"]
    rendered = template.render(data=body, custom_items=custom_items)

    os.makedirs(OUT_DIR, exist_ok=True)
    stem = template_name[:-5]
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = ".paged" if paged else ""
    html_out = wrap_paged(rendered) if paged else rendered
    html_path = os.path.join(OUT_DIR, f"{stem}_{ts}{suffix}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"  HTML: {html_path}" + ("  (Paged.js A4-превью)" if paged else ""))

    if pdf:
        # Chrome пагинирует сам → отдаём ему ПЛОСКИЙ HTML (без Paged.js-обёртки)
        if paged:
            plain_path = os.path.join(OUT_DIR, f"{stem}_{ts}.plain.html")
            with open(plain_path, "w", encoding="utf-8") as f:
                f.write(rendered)
        else:
            plain_path = html_path
        pdf_path = os.path.join(OUT_DIR, f"{stem}_{ts}.pdf")
        render_pdf_chrome(plain_path, pdf_path)

    return html_path


# ---------- Paged.js превью (разбивка на A4-страницы в браузере) ----------

# Fallback-@page для темплейтов, которые сами не задают @page (вставляется РАНО,
# чтобы свой @page темплейта мог его переопределить).
PAGED_FALLBACK = """
<style id="pagedjs-fallback">
@page {
    size: A4 portrait;
    margin: 12mm;
    @bottom-right { content: "Page " counter(page) " / " counter(pages); font: 8pt Arial, sans-serif; color: #555; }
}
</style>
"""

# Фон-«стол», тени листов и сам Paged.js (вставляется ПОЗДНО, чтобы фон победил).
PAGED_BACKDROP = """
<style id="pagedjs-backdrop">
body { background: #8f8f8f !important; }
.pagedjs_page { background: #ffffff; box-shadow: 0 0 0.4cm rgba(0,0,0,0.45); margin: 0 auto 8mm auto; }
</style>
<script src="https://unpkg.com/pagedjs/dist/paged.polyfill.js"></script>
"""


def wrap_paged(html):
    """Вставляет Paged.js + превью-стили, чтобы браузер разложил HTML по A4-листам."""
    lower = html.lower()
    # fallback-@page — сразу после <head> (низкий приоритет, перебивается темплейтом)
    h = lower.find("<head>")
    if h != -1:
        html = html[:h + 6] + PAGED_FALLBACK + html[h + 6:]
        lower = html.lower()
    # фон + скрипт — перед </head> (высокий приоритет)
    idx = lower.rfind("</head>")
    if idx != -1:
        return html[:idx] + PAGED_BACKDROP + html[idx:]
    return PAGED_BACKDROP + html


def list_templates():
    return sorted(f for f in os.listdir(TEMPLATES_DIR) if f.endswith(".html"))


def main():
    args = sys.argv[1:]
    paged = "--paged" in args
    pdf = "--pdf" in args
    args = [a for a in args if a not in ("--paged", "--pdf")]
    if not args:
        print(__doc__)
        print("Доступные темплейты:")
        for t in list_templates():
            print("  -", t)
        return

    if args[0] == "--all":
        payload = args[1] if len(args) > 1 else DEFAULT_PAYLOAD
        with open(os.path.join(PAYLOADS_DIR, payload), encoding="utf-8") as f:
            base = f.read()
        for t in list_templates():
            print(f"\n[{t}] payload={payload}")
            body = process_payload(json.loads(base))  # свежая копия на каждый темплейт
            render_one(t, body, paged=paged, pdf=pdf)
        return

    template_name = args[0]
    payload = args[1] if len(args) > 1 else DEFAULT_PAYLOAD
    with open(os.path.join(PAYLOADS_DIR, payload), encoding="utf-8") as f:
        body = json.load(f)
    body = process_payload(body)
    print(f"[{template_name}] payload={payload}")
    render_one(template_name, body, paged=paged, pdf=pdf)


if __name__ == "__main__":
    main()
