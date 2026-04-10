from jinja2 import Template
import pdfkit
import datetime
import os
from flask import request
import re
import json
import math
from urllib.parse import urlsplit

ROOT_URL = os.environ.get("ROOT_URL", "http://localhost")


def _sum_change_order_grand_total(categories):
    total = 0.0
    for cat in categories or []:
        for subcat in cat.get("subcategories") or []:
            for item in subcat.get("items") or []:
                if item.get("omitFromPDF"):
                    continue
                raw = item.get("total")
                if raw is None or raw == "N/A":
                    continue
                s = str(raw).replace(",", "").replace("$", "").strip()
                try:
                    total += float(s)
                except ValueError:
                    continue
    return total


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

def make_change_order():
    body = request.json
    with open('./templates/change_order.html') as f:
        jinja_t = Template(f.read())
    jinja_t.environment.filters["linkify"] = linkify_urls

    sqFt = body['estimatesInfo'][0]['squareFootage']  # used below in exp evaluation
    for cat in body['categories']:
        cat['totalFormatted'] = f"{cat['total'] :,}"

        for subcat in cat['subcategories']:
            for item in subcat['items']:
                if item.get('priceHidden', False):
                    item['price'] = "N/A"
                    item['total'] = "N/A"
                addi = item.get("additionalInfo") or ""
                if addi and "EXP[" in addi and "]EXP" in addi:
                    expressions = re.findall(r"EXP\[(.*?)\]EXP", addi)
                    item["additionalInfo"] = addi.replace("EXP[", "").replace("]EXP", "")
                    for expression in expressions:
                        result = eval(expression)
                        item["additionalInfo"] = item["additionalInfo"].replace(expression, str(result))
                if "EXP[" in item['longDescription'] and "]EXP" in item['longDescription']:
                    expressions = re.findall(r'EXP\[(.*?)\]EXP', item['longDescription'])
                    item['longDescription'] = item['longDescription'].replace("EXP[", "").replace("]EXP", "")
                    for expression in expressions:
                        result = eval(expression)
                        item['longDescription'] = item['longDescription'].replace(expression, str(result))

    body["grandTotalFormatted"] = f"${_sum_change_order_grand_total(body.get('categories')):,.2f}"

    rendered = jinja_t.render(data=body)
    ts = datetime.datetime.now().timestamp()
    if not os.path.exists('./static'):
        os.makedirs('./static')
    pdfkit.from_string(rendered, f"./static/change_order_{ts}.pdf")

    response = {
        'statusCode': 200,
        'body': {
            "change_order": f"{ROOT_URL}/static/change_order_{ts}.pdf",
            "data": json.dumps(body)
        }
    }
    return response


make_change_order.methods = ['POST']
