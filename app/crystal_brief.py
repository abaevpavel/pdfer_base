from jinja2 import Template
import pdfkit
import datetime
import os
import json
from flask import request

ROOT_URL = os.environ.get("ROOT_URL", "http://localhost")

# Палитра-акцент по доминирующей оси DISC: (основной цвет, светлый фон-плашка).
DISC_ACCENT = {
    "D": ("#C0392B", "#f7e4e1"),  # Dominance - красный
    "I": ("#E67E22", "#fbeede"),  # Influence - оранжевый
    "S": ("#27AE60", "#e2f4ea"),  # Steadiness - зелёный
    "C": ("#2F5F8F", "#e3ebf3"),  # Conscientiousness - синий
}

DISC_FAMILY = {
    "D": "Dominance - result-driven, fast, in control",
    "I": "Influence - social, enthusiastic, big-picture",
    "S": "Steadiness - steady, supportive, trust-driven",
    "C": "Conscientiousness - logical, precise, detail-driven",
}

# Цвет баннера уровня доверия (accent / soft-фон).
CONF_COLOR = {
    "High": ("#1f7a3d", "#e4f1e9"),
    "Medium": ("#B8860B", "#f7efda"),
    "Low": ("#C0392B", "#f7e4e1"),
}


def _int(v, default=0):
    try:
        return int(round(float(str(v).strip())))
    except (ValueError, TypeError, AttributeError):
        return default


def _primary_axis(pct, disc_type):
    """Доминирующая ось = ось с МАКСИМАЛЬНЫМ реальным процентом DISC
    (а не первая буква disc_type)."""
    if pct:
        items = [(k.upper(), _int(v)) for k, v in pct.items() if k.upper() in DISC_ACCENT]
        if items:
            items.sort(key=lambda kv: kv[1], reverse=True)
            if items[0][1] > 0:
                return items[0][0]
    d = (disc_type or "C").strip()
    return d[0].upper() if d else "C"


def _confidence(intensity, pct, verified):
    """Уровень доверия из РЕАЛЬНЫХ чисел Crystal (disc_intensity + verified +
    чистота раскладки). Само число intensity не выдумываем - берём как есть."""
    vals = sorted(_int(v) for v in (pct or {}).values())
    clean = len(vals) >= 2 and vals[0] <= 5 and vals[1] <= 5
    if verified:
        return "High", clean
    if intensity >= 60:
        level = "High"
    elif intensity >= 35:
        level = "Medium"
    else:
        level = "Low"
    if clean and level != "High":
        level = {"Low": "Medium", "Medium": "High"}[level]
    return level, clean


def _confidence_note(intensity, verified, clean):
    """Честный note из реальных чисел - без свободной отсебятины ИИ."""
    if verified:
        return ("Verified Crystal assessment - the prospect completed the test, "
                "so this is a reliable read. Still, confirm key traits live early on.")
    if intensity >= 70:
        strength = "a strong signal"
    elif intensity >= 60:
        strength = "a solid signal"
    elif intensity >= 35:
        strength = "a moderate signal"
    else:
        strength = "a weak signal"
    clean_txt = " and the type read is clean (two DISC axes near zero)" if clean else ""
    return ("Predicted from public data (LinkedIn, etc.), not a taken Crystal test; "
            f"intensity {intensity}/100 is {strength}{clean_txt}. "
            "Verify the key traits live in your first few minutes.")


def normalize(brief):
    """Достраивает brief-JSON: уровень доверия и note считаем САМИ из реальных
    чисел (поля confidence/confidence_note от ИИ игнорируем), accent/family - по
    максимальной оси DISC, цвет баннера - по вычисленному уровню."""
    b = dict(brief or {})
    pct = b.get("disc_percentages") or {}
    intensity = _int(b.get("intensity"))
    verified = bool(b.get("verified"))

    primary = _primary_axis(pct, b.get("disc_type"))
    accent, accent_soft = DISC_ACCENT.get(primary, DISC_ACCENT["C"])

    level, clean = _confidence(intensity, pct, verified)
    conf_color, conf_soft = CONF_COLOR.get(level, CONF_COLOR["Medium"])

    b["intensity"] = intensity
    b["confidence"] = level
    b["confidence_note"] = _confidence_note(intensity, verified, clean)
    b["accent"] = accent
    b["accent_soft"] = accent_soft
    b["family"] = DISC_FAMILY.get(primary, "")
    b["conf_color"] = conf_color
    b["conf_soft"] = conf_soft
    b["verified_label"] = "verified test" if verified else "predicted"

    b.setdefault("disc_percentages", {})
    b.setdefault("behavioral_traits", {})
    for key in ("qualities", "do", "dont", "how_to_close", "watch_outs",
                "strengths", "motivation"):
        b.setdefault(key, [])
    for key in ("name", "disc_type", "archetype", "mbti", "overview", "summary",
                "golden_rule", "tone", "bottom_line", "url"):
        b.setdefault(key, "")
    return b


def _render(template_name, b):
    with open(f'./templates/{template_name}') as f:
        return Template(f.read()).render(b=b)


def make_crystal_brief():
    body = request.json
    # Принимаем сам brief-объект, либо обёртки [ {...} ] / { "brief": {...} }.
    if isinstance(body, list):
        body = body[0] if body else {}
    if isinstance(body, dict) and "brief" in body and isinstance(body["brief"], dict):
        body = body["brief"]

    b = normalize(body)

    if not os.path.exists('./static'):
        os.makedirs('./static')
    ts = datetime.datetime.now().timestamp()

    # Один двухстраничный PDF: стр.1 — короткий вариант, стр.2+ — полный
    # (один A4-шаблон с page-break, общий стиль — без отдельного short-PDF).
    brief_path = f"./static/crystal_brief_{ts}.pdf"
    opts = {"enable-local-file-access": None}
    pdfkit.from_string(_render('sales_brief_2page.html', b), brief_path, options=opts)

    return {
        'statusCode': 200,
        'body': {
            "brief": f"{ROOT_URL}/static/crystal_brief_{ts}.pdf",
            "data": json.dumps(b),
        }
    }


make_crystal_brief.methods = ['POST']
