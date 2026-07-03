from jinja2 import Environment, FileSystemLoader
import pdfkit
import datetime
import os
import re
import json
import math
import unicodedata
from decimal import Decimal
from flask import request
from urllib.parse import urlsplit

ROOT_URL = os.environ.get("ROOT_URL", "http://localhost")

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


# ---------- Jinja-фильтры (порт из forge_builder/render.py) ----------

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


# ---------- Препроцессинг payload'а (порт из forge_builder/render.py) ----------

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
        # ВАЖНО: на Change Order цену НЕ скрываем — ни для client, ни для internal
        # (правило: priceHidden в СО ничего не прячет; исключение только subcontractor,
        #  где колонки цены нет вообще). Поэтому здесь total/price НЕ блэнкаем в "N/A".

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


def make_change_order_internal():
    body = request.json
    # На этот эндпоинт payload приходит обёрнутым в массив ([{...}]) — разворачиваем в объект
    if isinstance(body, list):
        body = body[0] if body else {}

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=False)
    env.filters["linkify"] = linkify_urls
    env.filters["money"] = money
    template = env.get_template("change_order_internal.html")

    body = process_payload(body)
    rendered = template.render(data=body)

    ts = datetime.datetime.now().timestamp()
    if not os.path.exists('./static'):
        os.makedirs('./static')
    pdfkit.from_string(rendered, f"./static/change_order_internal_{ts}.pdf")

    response = {
        'statusCode': 200,
        'body': {
            "change_order_internal": f"{ROOT_URL}/static/change_order_internal_{ts}.pdf",
            "data": json.dumps(body)
        }
    }
    return response


make_change_order_internal.methods = ['POST']
