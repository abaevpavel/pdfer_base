from jinja2 import Template
import pdfkit
import datetime
import os
import json
from flask import request

ROOT_URL = os.environ.get("ROOT_URL", "http://localhost")

# Палитра-акцент по доминирующей оси DISC (первая буква disc_type):
# accent — основной цвет, soft — светлый фон-плашка (solid, без alpha — для wkhtmltopdf).
DISC_ACCENT = {
    "D": ("#C0392B", "#f7e4e1"),  # Dominance — красный
    "I": ("#E67E22", "#fbeede"),  # Influence — оранжевый
    "S": ("#27AE60", "#e2f4ea"),  # Steadiness — зелёный
    "C": ("#2F5F8F", "#e3ebf3"),  # Conscientiousness — синий
}

DISC_FAMILY = {
    "D": "Dominance - result-driven, fast, in control",
    "I": "Influence - social, enthusiastic, big-picture",
    "S": "Steadiness - steady, supportive, trust-driven",
    "C": "Conscientiousness - logical, precise, detail-driven",
}

# Цвет баннера уровня доверия Crystal (accent / soft-фон).
CONF_COLOR = {
    "High": ("#1f7a3d", "#e4f1e9"),
    "Medium": ("#B8860B", "#f7efda"),
    "Low": ("#C0392B", "#f7e4e1"),
}


def normalize(brief):
    """Добавляет к brief-JSON презентационные поля (accent/soft по disc_type,
    цвет баннера по confidence) и проставляет дефолты. Это делает бек, не ИИ."""
    b = dict(brief or {})

    disc = str(b.get("disc_type") or "C").strip()
    primary = disc[0].upper() if disc else "C"
    accent, accent_soft = DISC_ACCENT.get(primary, DISC_ACCENT["C"])
    conf = str(b.get("confidence") or "Medium").title()
    conf_color, conf_soft = CONF_COLOR.get(conf, CONF_COLOR["Medium"])

    b["accent"] = accent
    b["accent_soft"] = accent_soft
    b["family"] = b.get("family") or DISC_FAMILY.get(primary, "")
    b["confidence"] = conf
    b["conf_color"] = conf_color
    b["conf_soft"] = conf_soft

    b.setdefault("disc_percentages", {})
    b.setdefault("behavioral_traits", {})
    for key in ("qualities", "do", "dont", "how_to_close", "watch_outs",
                "strengths", "motivation"):
        b.setdefault(key, [])
    for key in ("name", "disc_type", "archetype", "mbti", "overview", "summary",
                "confidence_note", "golden_rule", "tone", "bottom_line", "url"):
        b.setdefault(key, "")
    b.setdefault("intensity", "")
    b.setdefault("verified", False)
    return b


def make_crystal_brief():
    body = request.json
    # Принимаем как сам brief-объект, так и обёртки [ {...} ] / { "brief": {...} }.
    if isinstance(body, list):
        body = body[0] if body else {}
    if isinstance(body, dict) and "brief" in body and isinstance(body["brief"], dict):
        body = body["brief"]

    b = normalize(body)

    with open('./templates/sales_brief.html') as f:
        jinja_t = Template(f.read())
    rendered = jinja_t.render(b=b)

    ts = datetime.datetime.now().timestamp()
    if not os.path.exists('./static'):
        os.makedirs('./static')
    out = f"./static/crystal_brief_{ts}.pdf"
    pdfkit.from_string(rendered, out, options={"enable-local-file-access": None})

    return {
        'statusCode': 200,
        'body': {
            "brief": f"{ROOT_URL}/static/crystal_brief_{ts}.pdf",
            "data": json.dumps(b),
        }
    }


make_crystal_brief.methods = ['POST']
