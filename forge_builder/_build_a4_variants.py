#!/usr/bin/env python3
"""
Одноразовый билд-хелпер: генерирует 7 A4-вариантов темплейтов из общих кусков,
по образцу вылизанного initial_client_scope_a4.html.

Выходные файлы — САМОДОСТАТОЧНЫЕ (стиль скопирован внутрь каждого), как в проде.
Запуск:  ../.venv/bin/python _build_a4_variants.py
"""
import os

TPL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


def style_block(footer_label, two_col=False):
    if two_col:
        width_css = (".table td:first-child { width: 82%; }\n"
                     "        .table td.num, .table td.col-label { width: 18%; }")
    else:
        width_css = (".table td:first-child { width: 72%; }\n"
                     "        .table td.num, .table td.col-label { width: 14%; }")
    return r'''<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <style>
        @page {
            size: A4 portrait;
            margin: 14mm 0 12mm 0;
            @bottom-left   { content: "__FOOTER__"; background: #2F5F8F; color: #FFFFFF; font: bold 8pt Arial, sans-serif; vertical-align: middle; padding-left: 12mm; border-top: 8pt solid #FFFFFF; }
            @bottom-center { content: " "; background: #2F5F8F; border-top: 8pt solid #FFFFFF; }
            @bottom-right  { content: "Page " counter(page) " / " counter(pages); background: #2F5F8F; color: #FFFFFF; font: 8pt Arial, sans-serif; vertical-align: middle; padding-right: 12mm; border-top: 8pt solid #FFFFFF; }
        }
        @page :first {
            margin: 0 0 12mm 0;
            @bottom-left   { content: "__FOOTER__"; background: #2F5F8F; color: #FFFFFF; font: bold 8pt Arial, sans-serif; vertical-align: middle; padding-left: 12mm; border-top: 8pt solid #FFFFFF; }
            @bottom-center { content: " "; background: #2F5F8F; border-top: 8pt solid #FFFFFF; }
            @bottom-right  { content: "Page " counter(page) " / " counter(pages); background: #2F5F8F; color: #FFFFFF; font: 8pt Arial, sans-serif; vertical-align: middle; padding-right: 12mm; border-top: 8pt solid #FFFFFF; }
        }

        html, body { margin: 0; padding: 0; font-family: Arial, Helvetica, sans-serif; color: #333333; font-size: 10pt; }

        .page-pad { padding: 6mm 12mm 0 12mm; }

        .doc-banner { background: #2F5F8F; color: #FFFFFF; padding: 16pt 28pt; font-size: 18pt; font-weight: bold; letter-spacing: 0.5pt; }
        .sqft { font-size: 14pt; font-weight: bold; color: #222222; margin: 16pt 0 10pt 0; }
        .intro { font-size: 9pt; line-height: 13pt; }
        .intro b { color: #222222; }

        .table { width: 100%; border-collapse: collapse; margin-top: 12pt; table-layout: fixed; }
        .table td { border: 0.75pt solid #C9C9C9; vertical-align: top; padding: 6pt 8pt; word-wrap: break-word; overflow-wrap: break-word; }

        .cat td { background: #4A78A6; color: #FFFFFF; border-color: #4A78A6; font-weight: bold; font-size: 10.5pt; padding: 7pt 8pt; }
        .cat-total { text-align: center; font-size: 11pt; }

        .subcat td { background: #E4E9F0; color: #333333; font-weight: bold; font-size: 9.5pt; }
        .col-label { text-align: center; font-weight: normal; color: #555555; }

        /* фиксируем ширины на ячейках — переживает разрыв таблицы между страницами */
        __WIDTH_CSS__

        .item-title { font-weight: bold; color: #1a1a1a; font-size: 10pt; margin: 0 0 4pt 0; }
        .item-desc  { color: #444444; font-size: 9pt; line-height: 13pt; orphans: 3; widows: 3; }
        .item-desc p { margin: 4pt 0; }
        .num { text-align: center; color: #555555; }

        .red { color: #C0392B; }
        .item-pricing-separator { color: #C9C9C9; margin: 6pt 0; }
        .owner-initials { margin-top: 8pt; font-size: 9pt; }
        .owner-initials .line { display: inline-block; border-bottom: 0.75pt solid #999; width: 150pt; }
        ul { margin: 4pt 0 4pt 0; padding-left: 16pt; }
        li { margin: 2pt 0; }

        .grand-total { margin-top: 14pt; font-size: 13pt; font-weight: bold; color: #2F5F8F; }

        /* item рвётся по странице без маркера; keep-группа держит шапки + первый item */
        .table, .table tr, .table td { page-break-inside: auto; break-inside: auto; }
        tbody.keep { break-inside: avoid; page-break-inside: avoid; }
    </style>
    <meta name="pdfkit-orientation" content="Portrait">
</head>
<body>
'''.replace("__FOOTER__", footer_label).replace("__WIDTH_CSS__", width_css)


# ---------- макросы по «вкусам» ----------

MACROS_REFUND = r'''
{% macro pricing_separator() -%}
<p class="item-pricing-separator">________________________________________________________________________</p>
{%- endmacro %}
{% macro maximum_refund_amount(it) -%}
{% set refund_str = it.maxRefundAmount | default('', true) | string | trim %}
{% if refund_str and refund_str | upper != 'N/A' %}
<p class="red"><b>Maximum refund amount:</b> {% if refund_str[0:1] == '$' %}{{ refund_str }}{% else %}${{ refund_str }}{% endif %}
<br/><span style="color:#444444;"><i>Maximum refund amount available after contract signing, based on incentives applied at the time of signing.</i></span></p>
{% endif %}
{%- endmacro %}
{% macro item_pricing_footer(it) -%}
{% set refund_str = it.maxRefundAmount | default('', true) | string | trim %}
{% if refund_str and refund_str | upper != 'N/A' and not it.priceHidden %}
{{ pricing_separator() }}{{ maximum_refund_amount(it) }}
{% endif %}
{%- endmacro %}
'''

MACROS_INTERNAL = MACROS_REFUND + r'''
{% macro internal_lines(it) -%}
{% if it.internalInstructions %}
<p class="red"><b>INTERNAL INSTRUCTIONS:</b><br/>
{{ it.internalInstructions | default('', true) | linkify | replace('\r\n','\n') | replace('\n','<br>') | replace('<br>-','<br>- ') | safe }}</p>
{% endif %}
{% if it.internalNotes %}
<p class="red"><b>INTERNAL NOTES:</b><br/>
{{ it.internalNotes | default('', true) | linkify | replace('\r\n','\n') | replace('\n','<br>') | replace('<br>-','<br>- ') | safe }}</p>
{% endif %}
{%- endmacro %}
{% macro custom_our_cost(it) -%}
{% set cd = it.customData | default({}) %}
{% if (cd.itemType | default('default')) != 'note' %}
<p class="red"><b>OUR COST:</b><br/>
Subcontractor proposal amount: {{ cd.subcontractorProposalAmount | default(0) | money }}<br/>
In house team cost: {{ cd.inHouseTeamCost | default(0) | money }}<br/>
Other cost: {{ cd.materialsAdminCost | default(0) | money }}<br/>
Recommended cost: {{ cd.recommendedCost | default(0) | money }}</p>
{% endif %}
{%- endmacro %}
{% macro catalog_price_description(it) -%}
{% if it.catelogId == 'Custom' %}{% set price_str = it.quantity | money %}{% else %}{% set price_str = it.price | money %}{% endif %}
{% if price_str and price_str | upper != 'N/A' and price_str | upper != 'CUSTOM' %}
<p class="red"><b>Catalog Price Description:</b> {{ price_str }}<br/><span style="color:#444444;"><i>Catalog price shown for reference only and not visible to the customer.</i></span></p>
{% endif %}
{%- endmacro %}
{% macro item_pricing_footer_internal(it) -%}
{% if it.catelogId == 'Custom' %}{% set price_str = it.quantity | money %}{% else %}{% set price_str = it.price | money %}{% endif %}
{% set refund_str = it.maxRefundAmount | default('', true) | string | trim %}
{% set show_catalog = price_str and price_str | upper != 'N/A' and price_str | upper != 'CUSTOM' %}
{% set show_refund = refund_str and refund_str | upper != 'N/A' and not it.priceHidden %}
{% if show_catalog or show_refund %}
{{ pricing_separator() }}
{% if show_catalog %}{{ catalog_price_description(it) }}{% endif %}
{% if show_refund %}{{ maximum_refund_amount(it) }}{% endif %}
{% endif %}
{%- endmacro %}
{# CO-вариант: каталожная цена есть, max refund НЕ показываем (741: на СО убираем) #}
{% macro item_pricing_footer_internal_co(it) -%}
{% if it.catelogId == 'Custom' %}{% set price_str = it.quantity | money %}{% else %}{% set price_str = it.price | money %}{% endif %}
{% set show_catalog = price_str and price_str | upper != 'N/A' and price_str | upper != 'CUSTOM' %}
{% if show_catalog %}
{{ pricing_separator() }}{{ catalog_price_description(it) }}
{% endif %}
{%- endmacro %}
'''

# общая «шапка» описания item (заголовок + addi + longDescription + фото)
DESC_HEAD = r'''{% if item.catelogId == 'Custom' %}
                                {% set item_type = (item.customData | default({})).itemType | default('default') %}
                                <p class="item-title">{% if item_type == 'credit' %}Custom Credit item:{% elif item_type == 'note' %}Custom Note item:{% else %}Custom item:{% endif %} {{ item.name }}</p>
                                {% set addi = item.additionalInfo | default('') | trim %}
                                {% if addi %}{{ addi | e | linkify | replace('\r\n','\n') | replace('\n','<br>') | replace('<br>-','<br>- ') | safe }}{% endif %}
                            {% else %}
                                <p class="item-title">ITEM {{ item.catelogId }}. {{ item.name }}</p>
                                {% set addi = item.additionalInfo | default('') | trim %}
                                {% if addi %}<p><b>ADDITIONAL NOTE:</b></p>{{ addi | e | linkify | replace('\r\n','\n') | replace('\n','<br>') | replace('<br>-','<br>- ') | safe }}{% endif %}
                                {{ item.longDescription | linkify | safe }}
                            {% endif %}
                            {% set has_photos = item.photos is defined and item.photos and (item.photos | select | list | length > 0) %}
                            {% if has_photos %}<p><a href="https://info.basementremodeling.com/guide_details/{{ item.id }}" style="color:#2F5F8F;">Click here for details</a></p>{% endif %}'''

OWNER_INITIALS = '\n                            <div class="owner-initials"><b>Owner Initials:</b> <span class="line"></span></div>'

DESC_CLIENT   = DESC_HEAD + '\n                            {{ item_pricing_footer(item) }}' + OWNER_INITIALS
DESC_INTERNAL = DESC_HEAD + '\n                            {{ internal_lines(item) }}{% if item.catelogId == \'Custom\' %}{{ custom_our_cost(item) }}{% endif %}{{ item_pricing_footer_internal(item) }}'
DESC_SUB      = DESC_HEAD  # без цен/инициалов
# CO-варианты (741: на change order max refund НЕ показываем)
DESC_CLIENT_CO   = DESC_HEAD + OWNER_INITIALS
DESC_INTERNAL_CO = DESC_HEAD + '\n                            {{ internal_lines(item) }}{% if item.catelogId == \'Custom\' %}{{ custom_our_cost(item) }}{% endif %}{{ item_pricing_footer_internal_co(item) }}'

# числовые ячейки
NUM_CLIENT = r'''<td class="num">{% if item.catelogId == 'Custom' %}1{% else %}{{ item.quantity }}{% endif %}</td>
                    <td class="num">{% if item.total != "N/A" %}${{ item.total }}{% else %}N/A{% endif %}</td>'''
NUM_INTERNAL = r'''<td class="num">{% if item.catelogId == 'Custom' %}1{% else %}{{ item.quantity }}{% endif %}</td>
                    <td class="num">{{ item.total | money }}{% if item.priceHidden %}<br/><span style="color:#C0392B; font-size:8pt;">(hidden)</span>{% endif %}</td>'''
NUM_SUB = r'''<td class="num">{% if item.catelogId == 'Custom' %}{% if item.total == "N/A" %}N/A{% else %}1{% endif %}{% else %}{{ item.quantity }}{% endif %}</td>'''

# colgroup и шапки
COLGROUP_3 = '<colgroup><col style="width:72%;"><col style="width:14%;"><col style="width:14%;"></colgroup>'
COLGROUP_2 = '<colgroup><col style="width:82%;"><col style="width:18%;"></colgroup>'
CAT_3 = '<td>{{ category.id }} {{ category.name }}</td>\n                    <td class="cat-total" colspan="2">${{ category.totalFormatted }}</td>'
CAT_2 = '<td colspan="2">{{ category.id }} {{ category.name }}</td>'
SUBCAT_3 = '<td>{{ subcategory.name }}</td>\n                    <td class="col-label">Quantity</td>\n                    <td class="col-label">Total</td>'
SUBCAT_3_INTERNAL = "<td>{{ subcategory.name }}</td>\n                    <td class=\"col-label\">Quantity</td>\n                    <td class=\"col-label\">Client's Price based on Zone</td>"
SUBCAT_2 = '<td>{{ subcategory.name }}</td>\n                    <td class="col-label">Quantity</td>'


def build_body(banner, intros, desc, num_cells, colgroup, cat_header, subcat_header,
               macros, pre_tables="", post_tables="", sqft=False):
    intro_html = ""
    if sqft:
        intro_html += '        <div class="sqft">PROJECT TOTAL SQ. FT. = {{ data[\'estimatesInfo\'][0][\'squareFootage\'] }} SQ. FT.</div>\n'
    for para in intros:
        intro_html += '        <p class="intro"><b>' + para + '</b></p>\n'

    tables = r'''
        {% for category in data['categories'] %}
        <table class="table" cellspacing="0">
            __COLGROUP__
            {% for subcategory in category.subcategories %}
            <tbody class="keep">
                {% if loop.first %}
                <tr class="cat">
                    __CAT_HEADER__
                </tr>
                {% endif %}
                <tr class="subcat">
                    __SUBCAT_HEADER__
                </tr>
            </tbody>
            <tbody>
                {% for item in subcategory['items'] %}
                {% if not item['omitFromPDF'] %}
                <tr>
                    <td>
                        <div class="item-desc">
                            __DESC__
                        </div>
                    </td>
                    __NUM__
                </tr>
                {% endif %}
                {% endfor %}
            </tbody>
            {% endfor %}
        </table>
        {% endfor %}
'''
    tables = (tables.replace("__COLGROUP__", colgroup)
                    .replace("__CAT_HEADER__", cat_header)
                    .replace("__SUBCAT_HEADER__", subcat_header)
                    .replace("__DESC__", desc)
                    .replace("__NUM__", num_cells))

    return (macros
            + '\n    <div class="doc-banner">' + banner + '</div>\n'
            + '    <div class="page-pad">\n'
            + intro_html
            + pre_tables
            + tables
            + post_tables
            + '    </div>\n</body>\n</html>\n')


SEPTIC = ("ATTENTION! PROPERTY ON SEPTIC? BEDROOMS OR ROOMS WITH CLOSETS ARE NOT POSSIBLE UNLESS WRITTEN CONFIRMATION "
          "FROM COUNTY/CITY HEALTH DEPARTMENT IS PROVIDED! THIS INCLUDES REMODELING PROJECTS WITH EXISTING ROOMS!")
UNITPRICE = ("UNIT PRICING MAY NOT BE STRICTLY LINEAR AND MAY INCLUDE BUNDLED PRICING FORMULAS OR OTHER PRICING FACTORS. "
             "AS A RESULT, INDIVIDUAL UNIT COSTS MAY VARY AND MAY NOT EQUAL THE TOTAL PRICE DIVIDED BY THE QUANTITY.")

GRAND_TOTAL = '        <div class="grand-total">Total Cost: {{ data.grandTotalFormatted }}</div>\n'


def write(name, footer, body, two_col=False):
    html = style_block(footer, two_col=two_col) + body
    path = os.path.join(TPL_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print("written:", name)


# ---------------- сборка 7 вариантов ----------------

# 1. initial_internal_scope_a4
write("initial_internal_scope_a4.html", "INTERNAL SCOPE",
      build_body("ATTACHMENT 1: INTERNAL SCOPE", [SEPTIC, UNITPRICE],
                 DESC_INTERNAL, NUM_INTERNAL, COLGROUP_3, CAT_3, SUBCAT_3_INTERNAL,
                 MACROS_INTERNAL, sqft=True))

# 2. initial_subcontractor_scope_a4
write("initial_subcontractor_scope_a4.html", "SUBCONTRACTOR SCOPE",
      build_body("ATTACHMENT 1: SUBCONTRACTOR SCOPE", [SEPTIC],
                 DESC_SUB, NUM_SUB, COLGROUP_2, CAT_2, SUBCAT_2,
                 "", sqft=True), two_col=True)

# 3. initial_contract_a4 (= точная копия client, только название в шапке)
write("initial_contract_a4.html", "FULL PROJECT SCOPE",
      build_body("ATTACHMENT 1: CLIENT SCOPE (CONTRACT)", [SEPTIC, UNITPRICE],
                 DESC_CLIENT, NUM_CLIENT, COLGROUP_3, CAT_3, SUBCAT_3,
                 MACROS_REFUND, sqft=True))

# 4. change_order_client_a4
write("change_order_client_a4.html", "CHANGE ORDER",
      build_body("ATTACHMENT 1: CHANGE ORDER SCOPE", [UNITPRICE],
                 DESC_CLIENT_CO, NUM_CLIENT, COLGROUP_3, CAT_3, SUBCAT_3,
                 MACROS_REFUND, post_tables=GRAND_TOTAL))

# 5. change_order_internal_a4
write("change_order_internal_a4.html", "INTERNAL CHANGE ORDER",
      build_body("ATTACHMENT 1: INTERNAL CHANGE ORDER SCOPE", [UNITPRICE],
                 DESC_INTERNAL_CO, NUM_INTERNAL, COLGROUP_3, CAT_3, SUBCAT_3_INTERNAL,
                 MACROS_INTERNAL, post_tables=GRAND_TOTAL))

# 6. change_order_subcontractor_a4
write("change_order_subcontractor_a4.html", "SUBCONTRACTOR CHANGE ORDER",
      build_body("ATTACHMENT 1: SUBCONTRACTOR CHANGE ORDER SCOPE", [SEPTIC],
                 DESC_SUB, NUM_SUB, COLGROUP_2, CAT_2, SUBCAT_2,
                 ""), two_col=True)

# 7. change_order_contract_a4 (= точная копия change order client, только название в шапке)
write("change_order_contract_a4.html", "CHANGE ORDER",
      build_body("ATTACHMENT 1: CHANGE ORDER (CONTRACT)", [UNITPRICE],
                 DESC_CLIENT_CO, NUM_CLIENT, COLGROUP_3, CAT_3, SUBCAT_3,
                 MACROS_REFUND, post_tables=GRAND_TOTAL))

print("\nГотово: 7 A4-вариантов сгенерированы.")
