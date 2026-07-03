# Forge Document Builder — логика темплейтов и отображения items

Документ для разработчика. Описывает, **как устроены все темплейты** Forge и
**по каким условиям рендерятся items** в каждом из них.

> Источник истины — **базовые** темплейты в `forge_builder/templates/` (НЕ `*_a4`).
> `*_a4` — это редизайн под A4/синюю палитру, генерится из них же
> (`_build_a4_variants.py`); логика отображения items идентична базовым, отличается
> только вёрстка/пагинация. Поэтому ниже всё описано по базовым файлам.

---

## 1. Матрица темплейтов

Две сущности (Initial proposal / Change order) × четыре аудитории
(Client / Internal / Subcontractor / Contract) = **8 темплейтов**:

| Аудитория | Initial | Change order |
|---|---|---|
| **Client** | `initial_client_scope.html` | `change_order_client.html` |
| **Internal** | `initial_internal_scope.html` | `change_order_internal.html` |
| **Subcontractor** | `initial_subcontractor_scope.html` | `change_order_subcontractor.html` |
| **Contract** | `initial_contract.html` | `change_order_contract.html` |

По **структуре таблицы** уникальных видов фактически три (это, вероятно, и есть
«6 типов» из ТЗ, если считать сущности отдельно):

1. **Client / Contract** — одинаковая таблица: 3 колонки (Description / Quantity / Total).
   Различаются только заголовком и доп.страницами contract (cover/terms/signatures —
   пока плейсхолдеры, к items отношения не имеют).
2. **Internal** — те же 3 колонки + внутренние блоки (INTERNAL INSTRUCTIONS / NOTES,
   OUR COST, Catalog Price Description) + у `initial` отдельный сгруппированный блок custom-items.
3. **Subcontractor** — 2 колонки (Description / Quantity), **без цен**.

---

## 2. Общий конвейер данных (одинаков для всех)

Препроцессинг — `render.py::process_payload()` (повторяет прод-роуты). Применяется
к payload **до** рендера и трогает каждый item:

| Шаг | Что делает |
|---|---|
| `priceHidden == true` | проставляет `item.price = "N/A"`, `item.total = "N/A"` — **только для non-CO темплейтов**. На **Change Order цену НЕ скрываем** (`hide_prices=False`): ни client, ни internal, `total`/`price` остаются реальными |
| `EXP[...]EXP` | вычисляет python-выражение (в скоупе `sqFt`, `math`) внутри `additionalInfo` / `longDescription` / `internalInstructions` / `internalNotes` |
| `**текст**` | → `<b>текст</b>` (markdown-bold), только в `internalInstructions` / `internalNotes` |
| `category.totalFormatted` | `f"{total:,}"` — сумма категории с разделителями тысяч |
| `grandTotalFormatted` | `${...}` — общий итог (из `estimatesInfo[0].totalCost` либо сумма категорий) |

Jinja-фильтры:
- `linkify` — голые URL → `<a>домен - View Link</a>`.
- `money` — число/строку → `$1,234.56`. Используется только в **internal** и
  **change_order** темплейтах; client/subcontractor/contract `initial` выводят цену
  сырым `${{ item.total }}`.

`custom_items` передаётся в шаблон отдельным списком — это все items с
`catelogId == 'Custom'` по всему дереву (нужно только `initial_internal_scope`).

---

## 3. Обход дерева и базовые условия для item (во ВСЕХ темплейтах)

Цикл везде одинаков: `data.categories → category.subcategories → subcategory.items`.

```jinja
{% for item in subcategory['items'] %}
  {% if not item['omitFromPDF'] %}   ← айтем с omitFromPDF=true НЕ рендерится нигде
    ...
  {% endif %}
{% endfor %}
```

**Определение типа item:**
- Каталожный: `catelogId != 'Custom'`.
- Кастомный: `catelogId == 'Custom'` (+ `hasCustomPricing`, есть `customData`).

**Подтип кастома** — `customData.itemType` (`default` если нет):
| itemType | Заголовок строки |
|---|---|
| `credit` | `Custom Credit item:` |
| `note` | `Custom Note item:` |
| прочее/`default` | `Custom item:` |

Каталожный item всегда: `ITEM {catelogId}. {name}`.

**Тело описания (порядок вывода внутри ячейки Description):**

| Поле | Каталожный item | Кастомный item |
|---|---|---|
| Заголовок | `ITEM {catelogId}. {name}` | `Custom[/Credit/Note] item: {name}` |
| `additionalInfo` | под подзаголовком **ADDITIONAL NOTE:**, через `linkify` + переносы строк | сразу текст (без подзаголовка), `linkify` + переносы |
| `longDescription` | **выводится** (`linkify`) | **НЕ выводится** (у custom только `additionalInfo`) |
| `photos` (непустой) | ссылка `Click here for images` → `info.basementremodeling.com/guide_details/{id}` | то же |

> Перенос строк: `\r\n`/`\n` → `<br>`, а `<br>-` → `<br>- ` (буллеты).

**Колонка Quantity:**
- Каталожный → `item.quantity`.
- Кастомный → `1` (в subcontractor: `N/A`, если `item.total == "N/A"`, иначе `1`).

---

## 4. Что уникально для каждой аудитории

### 4.1 Client (`initial_client_scope`, `change_order_client`)

- **3 колонки:** Description (70%) / Quantity (10%) / Total (10%).
- Шапка категории: `{id} {name}` + `${{ category.totalFormatted }}`.
- Заголовок подкатегории + headers `Quantity` и `Total`.
- Колонка Total: `${{ item.total }}`, либо `N/A` если `item.total == "N/A"` (т.е. priceHidden).
- **Pricing footer под описанием:**
  - `initial`: разделитель (`item-pricing-separator`, серая линия 50%) +
    **Maximum refund amount** — показывается, только если `maxRefundAmount` задан,
    `!= "N/A"` и **не** `priceHidden`.
  - `change_order`: footer-макрос **пустой** → на CO refund НЕ показывается.
- `initial`: заголовок `ATTACHMENT 1: FULL PROJECT SCOPE.` + sqft + ATTENTION(septic) + unit-pricing disclaimer. **Нет** строки общего итога снизу (итоги по категориям).
- `change_order`: заголовок `ATTACHMENT 1: SCOPE OF WORK.` + только unit-pricing disclaimer. Снизу — `Total Cost: {{ grandTotalFormatted }}`.

### 4.2 Contract (`initial_contract`, `change_order_contract`)

Таблица и логика items **идентичны Client** (тот же footer: refund на initial,
пусто на CO). Отличия — только обвязка:
- Заголовки: `ATTACHMENT 1: CLIENT SCOPE (CONTRACT).` / `ATTACHMENT 1: CHANGE ORDER (CONTRACT).`
- По плану — доп. плейсхолдер-страницы (cover / terms / signatures), помеченные
  `[ PLACEHOLDER ]`; на рендер items не влияют.

### 4.3 Internal (`initial_internal_scope`, `change_order_internal`)

3 колонки, как у client, но **третья колонка названа `Client's Price based on Zone`**,
суммы через `| money`. Плюс внутренние блоки (рендерятся красным `.red`):

- **INTERNAL INSTRUCTIONS / INTERNAL NOTES** (`internal_lines`) — выводятся, если в
  item заданы `internalInstructions` / `internalNotes`. Markdown `**bold**` уже
  превращён в `<b>` препроцессингом.
- **OUR COST** (`custom_our_cost`) — только для **кастомных** items и только если
  `itemType != 'note'`. Поля из `customData`: `subcontractorProposalAmount`,
  `inHouseTeamCost`, `materialsAdminCost` (→ «Other cost»), `recommendedCost`.
- **Catalog Price Description** (`catalog_price_description`) — только для
  **каталожных** items (для custom НЕ показывается, осиротевшего разделителя тоже
  не остаётся). Цена: каталожный → `item.price | money`, скрывается если `N/A`/`Custom`.
- Колонка Total: `item.total | money`; если `priceHidden` — под ценой красным
  `(hidden from customer)`.
- У каталожных items красный цвет в `longDescription`/`additionalInfo`
  принудительно перекрашивается в чёрный (класс `.item-description`), чтобы красным
  оставались **только** внутренние блоки. У кастомных такой замены нет.

Различия двух internal-темплейтов:

| | `initial_internal_scope` | `change_order_internal` |
|---|---|---|
| Заголовок | `INTERNAL SCOPE: FULL PROJECT SCOPE.` | `ATTACHMENT 1: INTERNAL CHANGE ORDER SCOPE.` |
| Блок «CUSTOM ITEMS — GROUPED BY CATEGORY» сверху | **есть** (см. ниже) | нет |
| OUR COST для custom | только в верхнем сгруппированном блоке | **inline** в основной таблице |
| Catalog Price Description | для каталожных в основной таблице | для каталожных в основной таблице |
| Maximum refund amount | показывается (initial-правила) | **НЕ показывается** (на CO убран, BAS-741) |
| Итог снизу | нет | `Total Cost: {{ grandTotalFormatted }}` |

**Сгруппированный блок custom (только `initial_internal_scope`):** перед основным
разделом выводится `CUSTOM ITEMS — GROUPED BY CATEGORY` — те же custom-items,
сгруппированные по категории/подкатегории, с колонкой `Client's Price based on Zone`,
блоками INTERNAL и **OUR COST**. Основной раздел затем начинается с новой страницы
(`.next-section`, `page-break-before: always`). То есть OUR COST для кастомов в
`initial` живёт в этом верхнем блоке, а в основной таблице у кастома OUR COST нет.

### 4.4 Subcontractor (`initial_subcontractor_scope`, `change_order_subcontractor`)

- **2 колонки:** Description (80%) / Quantity (20%). **Цен нет вообще** — нет колонки
  Total, нет сумм категорий (`colspan=4`, шапка только с названием), нет grand total.
- Никаких pricing-footer'ов, INTERNAL-блоков, OUR COST, refund.
- Quantity для кастома: `N/A`, если `item.total == "N/A"`, иначе `1`.
- Заголовки: `ATTACHMENT 1: SUBCONTRACTOR SCOPE.` / `... SUBCONTRACTOR CHANGE ORDER SCOPE.`
- Шапка: ATTENTION(septic) есть; **unit-pricing disclaimer отсутствует**.

---

## 5. Сводная матрица условий

| Признак | Client init | Client CO | Contract init | Contract CO | Internal init | Internal CO | Subcontr init | Subcontr CO |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Колонок | 3 | 3 | 3 | 3 | 3 | 3 | 2 | 2 |
| Колонка Total / цена | ✅ | ✅ | ✅ | ✅ | ✅ (Zone) | ✅ (Zone) | ❌ | ❌ |
| Сумма категории | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Grand total снизу | ❌ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ |
| `omitFromPDF` скрывает item | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `longDescription` (каталог) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `longDescription` (custom) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Maximum refund amount | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Catalog Price Description (каталог) | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| OUR COST (custom, ≠note) | ❌ | ❌ | ❌ | ❌ | ✅¹ | ✅ | ❌ | ❌ |
| INTERNAL INSTRUCTIONS/NOTES | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| `(hidden from customer)` при priceHidden | ❌² | ❌² | ❌² | ❌² | ✅ | ❌⁴ | — | — |
| `money`-форматирование | ❌ | ✅³ | ❌ | ✅³ | ✅ | ✅ | — | — |
| Блок custom сверху | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |

¹ только в верхнем сгруппированном блоке custom-items.
² client/contract выводят цену как `N/A` (priceHidden уже превратил total в `"N/A"`), отдельной пометки нет.
³ grand total форматируется через `grandTotalFormatted`; цены items в client/contract `initial` — сырым `${{ item.total }}`.
⁴ на **internal CO** пометки «(hidden from customer)» нет: цену на СО не скрываем, `priceHidden` не блэнкает `total`, и приписка убрана (клиент цену на СО видит).

---

## 6. Где смотреть в коде

- Препроцессинг и фильтры: `forge_builder/render.py` (`process_payload`, `money`, `linkify_urls`).
- Темплейты: `forge_builder/templates/<name>.html` (макросы — в начале `<body>`).
- Прод-аналоги (та же логика): `app/proposal.py`, `app/change_order.py`,
  `app/internal_scope.py`, `app/subcontractor.py` + `app/templates/`.
- Модель payload: `basement/CLAUDE.md` → «Key data model».

---

## 7. Все условия отображения — человеческим языком

Полный список правил, по которым шаблон решает, что показывать. Сформулировано
словами (не кодом) — как спецификация для реализации в JS. В скобках указано,
в каких темплейтах правило действует.

### 7.0 Статичные блоки шапки документа

Это фиксированный текст в начале документа (от items не зависит). Присутствие
различается по темплейтам — таблица ниже.

- **Заголовок документа (h3)** — свой у каждого темплейта:
  - client init: «ATTACHMENT 1: FULL PROJECT SCOPE.»
  - internal init: «INTERNAL SCOPE: FULL PROJECT SCOPE.»
  - subcontractor init: «ATTACHMENT 1: SUBCONTRACTOR SCOPE.»
  - contract init: «ATTACHMENT 1: CLIENT SCOPE (CONTRACT).»
  - client CO: «ATTACHMENT 1: SCOPE OF WORK.»
  - internal CO: «ATTACHMENT 1: INTERNAL CHANGE ORDER SCOPE.»
  - subcontractor CO: «ATTACHMENT 1: SUBCONTRACTOR CHANGE ORDER SCOPE.»
  - contract CO: «ATTACHMENT 1: CHANGE ORDER (CONTRACT).»
- **SQ. FT. заголовок (h4)** — «BASEMENT TOTAL SQ. FT. = {squareFootage} SQ. FT.»
  (у subcontractor init текст «PROJECT TOTAL SQ. FT. = …»). Значение — из
  `estimatesInfo[0].squareFootage`.
- **ATTENTION (septic)** — фикс. предупреждение: *«ATTENTION! PROPERTY ON SEPTIC?
  BEDROOMS OR ROOMS WITH CLOSETS ARE NOT POSSIBLE UNLESS WRITTEN CONFIRMATION FROM
  COUNTY/CITY HEALTH DEPARTMENT IS PROVIDED! THIS INCLUDES REMODELING PROJECTS WITH
  EXISTING ROOMS!»*
- **UNIT PRICING** — фикс. дисклеймер: *«UNIT PRICING MAY NOT BE STRICTLY LINEAR AND
  MAY INCLUDE BUNDLED PRICING FORMULAS OR OTHER PRICING FACTORS. AS A RESULT,
  INDIVIDUAL UNIT COSTS MAY VARY AND MAY NOT EQUAL THE TOTAL PRICE DIVIDED BY THE
  QUANTITY.»*

Где какие блоки показываются:

| Блок | client init | client CO | contract init | contract CO | internal init | internal CO | subcontr init | subcontr CO |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Заголовок (h3) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| SQ. FT. (h4) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| ATTENTION (septic) | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ |
| UNIT PRICING | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |

> Закономерность в целом: **change order** не выводит SQ. FT. и (кроме subcontractor)
> ATTENTION; **subcontractor** не выводит UNIT PRICING. Но есть исключения, поэтому
> ориентируйся на таблицу, а не на правило.

### 7.1 Какие items вообще показываем (все темплейты)

- Идём по дереву: категории → подкатегории → items.
- Если у item стоит флаг **`omitFromPDF`** — этот item полностью пропускаем,
  не выводим его строку вообще.

### 7.2 Заголовок строки item (все темплейты)

- Если item **каталожный** (`catelogId` ≠ `"Custom"`) — заголовок:
  **«ITEM {catelogId}. {название}»**.
- Если item **кастомный** (`catelogId` = `"Custom"`) — смотрим `customData.itemType`:
  - `credit` → **«Custom Credit item: {название}»**
  - `note` → **«Custom Note item: {название}»**
  - любое другое или поле отсутствует → **«Custom item: {название}»**

### 7.3 Доп. примечание `additionalInfo` (все темплейты)

- Показываем, только если поле непустое (после обрезки пробелов). В internal-темплейтах
  дополнительно считаем пустыми буквальные строки `"None"` и `"none"` (их не показываем).
- Для **каталожного** item перед текстом печатаем подзаголовок **«ADDITIONAL NOTE:»**.
- Для **кастомного** item подзаголовка нет — сразу текст.
- В тексте ссылки превращаются в кликабельные, а переносы строк сохраняются
  (каждая новая строка — с новой строки, элементы списка с «- » выравниваются).

### 7.4 Подробное описание `longDescription`

- Показываем **только у каталожных** items. У кастомных `longDescription`
  **не показываем нигде** (у кастома из текста — только `additionalInfo`).
- В **internal**-темплейтах у каталожного item красный цвет внутри описания
  принудительно перекрашивается в чёрный (чтобы красным остались только внутренние
  блоки — см. 7.11–7.12). В остальных темплейтах описание выводится как есть.

### 7.5 Фотографии

- Если у item есть непустой список `photos` (хотя бы одно непустое значение) —
  показываем ссылку **«Click here for images»**, ведущую на
  `info.basementremodeling.com/guide_details/{id}`.

### 7.6 Колонка «Quantity»

- Каталожный item → показываем `quantity` из payload.
- Кастомный item → показываем **«1»**.
- Исключение для **subcontractor** (init и CO): кастомный item → **«N/A»**, если его
  `total` равен `"N/A"`, иначе **«1»**.

### 7.7 Колонка «Total» / цена

- **Client / Contract** (init и CO): если `total` ≠ `"N/A"` → показываем **«${total}»**;
  если `"N/A"` → показываем **«N/A»**.
  > `total` становится `"N/A"` автоматически, когда у item включён флаг `priceHidden`.
- **Internal init**: показываем отформатированную сумму `total`. Дополнительно,
  если у item включён `priceHidden` — под ценой красным мелким шрифтом приписка
  **«(hidden from customer)»**.
- **Internal CO**: показываем **реальную** сумму `total` (на СО цену не скрываем).
  Приписки «(hidden from customer)» **нет** — на change order клиент цену видит,
  так что пометка была бы вводящей в заблуждение.
- **Subcontractor**: колонки Total нет вообще.

> **Правило цены на Change Order:** в СО прайс **не скрываем никогда** — ни client,
> ни internal (`priceHidden` в контексте СО игнорируется, `total`/`price` остаются
> реальными). Единственное исключение — **subcontractor**, где колонки цены нет by design.

### 7.8 «Maximum refund amount» (под описанием)

Сам блок: показываем, если поле `maxRefundAmount` непустое и не равно `"N/A"`.
Значение выводим с «$» впереди (если его ещё нет). Текст: *«Maximum refund amount
after contract signing, based on incentives applied at the time of signing.»*

Где показываем:
- **Client init / Contract init** — показываем, если `maxRefundAmount` задан, не `"N/A"`
  **и** у item НЕ включён `priceHidden`. Перед блоком — серая линия-разделитель.
- **Client CO / Contract CO** — **не показываем** (на change order refund убран).
- **Internal init** — показываем по тем же условиям, что и client init (см. 7.10).
- **Internal CO** — **не показываем** (убран на CO, BAS-741).
- **Subcontractor** — не показываем.

### 7.9 «Catalog Price Description» (только internal-темплейты)

- Берём цену: у каталожного — `price`, у кастомного — `quantity` (так в шаблоне).
- Показываем блок, **только если item каталожный** (для кастомных не показываем)
  и цена непустая, не `"N/A"` и не `"CUSTOM"`.
- Текст-сноска: *«Catalog price shown for reference only and not visible to the
  customer; reflects pricing before zone adjustments and discounts.»*

### 7.10 Порядок блоков под описанием в internal

- **Internal init**: сначала решаем, показывать ли Catalog Price Description (правило 7.9)
  и показывать ли Maximum refund amount (правило 7.8 для client init). Если показываем
  хотя бы один из них — рисуем серую линию-разделитель, затем сам(и) блок(и):
  сначала Catalog Price, потом Maximum refund.
- **Internal CO**: то же, но **только Catalog Price Description** — refund на CO не выводится.

### 7.11 «OUR COST» (только internal, только для кастомных items)

- Показываем только у **кастомных** items и только если `customData.itemType` **≠ `note`**
  (у note-кастомов блока цены нет).
- Содержимое (из `customData`):
  - Subcontractor proposal amount → `subcontractorProposalAmount`
  - In house team cost → `inHouseTeamCost`
  - Other cost → `materialsAdminCost`
  - Recommended cost → `recommendedCost`
  - (отсутствующие поля считаем за 0)
- **Где именно показываем:**
  - **Internal init** — OUR COST для кастомов показываем **только в верхнем
    сгруппированном блоке** (см. 7.13). В основной таблице у кастома OUR COST **нет**.
  - **Internal CO** — OUR COST показываем **прямо в основной таблице** у каждого
    кастомного item.

### 7.12 «INTERNAL INSTRUCTIONS» / «INTERNAL NOTES» (только internal)

- Если у item задано `internalInstructions` — показываем блок **«INTERNAL INSTRUCTIONS:»**
  с этим текстом.
- Если задано `internalNotes` — показываем блок **«INTERNAL NOTES:»**.
- Если оба пустые — не показываем ничего.
- Жирный markdown (`**текст**`) в этих полях уже преобразован в жирный текст на этапе
  подготовки данных.

### 7.13 Верхний блок «CUSTOM ITEMS — GROUPED BY CATEGORY» (только `initial_internal_scope`)

- Показываем блок целиком, только если в проекте есть хотя бы один кастомный item.
- Внутри: проходим по категориям и подкатегориям и берём **только кастомные** items
  (`catelogId = "Custom"`). Подкатегории без кастомов пропускаем; шапку категории
  печатаем один раз — перед её первым кастомом.
- Для каждого кастома показываем: заголовок → `additionalInfo` → фото →
  INTERNAL INSTRUCTIONS/NOTES → **OUR COST** → (Catalog Price / refund по правилам 7.9–7.10).
  Quantity = «1»; Total = отформатированная сумма (+ «(hidden from customer)» при `priceHidden`).
- После этого блока **основной раздел начинается с новой страницы**.

### 7.13a Сводка: что показывается по ТИПУ айтема

Логика различает 5 типов (по `catelogId` и `customData.itemType`). Таблица — что
выводится для каждого типа (отдельно помечено, если только в internal).

| Что выводим | Каталожный (`catelogId`≠Custom) | Custom `default` | Custom `credit` | Custom `note` | Custom `materials` |
|---|---|---|---|---|---|
| Заголовок строки | «ITEM {catelogId}. {name}» | «Custom item: {name}» | «Custom Credit item: {name}» | «Custom Note item: {name}» | «Custom item: {name}» ¹ |
| `additionalInfo` | да, под подзаголовком «ADDITIONAL NOTE:» | да, сразу текстом (без подзаголовка) | да, сразу текстом | да, сразу текстом | да, сразу текстом |
| `longDescription` | **да** | **нет** | **нет** | **нет** | **нет** |
| Фото-ссылка | если есть `photos` | если есть | если есть | если есть | если есть |
| Колонка Quantity | `quantity` | «1» ² | «1» ² | «1» ² | «1» ² |
| Колонка Total/цена | да (где колонка есть) | да | да | да | да |
| **OUR COST** (internal) | **нет** (только у custom) | **да** | **да** | **НЕТ** ³ | **да** |
| **Catalog Price Description** (internal) | **да** (если цена валидна) | нет ⁴ | нет ⁴ | нет ⁴ | нет ⁴ |
| INTERNAL INSTR./NOTES (internal) | если заданы | если заданы | если заданы | если заданы | если заданы |
| Maximum refund (где применимо) | если `maxRefundAmount` валиден | если валиден | если валиден | если валиден | если валиден |

¹ `materials` логикой **не различается** — попадает в общую ветку «Custom item:» (открытый вопрос 8.5).
² subcontractor: «N/A», если `total == "N/A"`, иначе «1».
³ **note-кастом — единственный тип, у которого OUR COST не показываем** (правило `itemType != 'note'`, см. 7.11).
⁴ у кастомов Catalog Price Description не показывается (блок только для каталожных, см. 7.9); при этом для кастома в качестве «цены» берётся `quantity` — но условие `catelogId != Custom` всё равно его отсекает.

> Где OUR COST физически появляется: internal init — только в верхнем сгруппированном
> блоке custom; internal CO — inline в основной таблице. В client/contract/subcontractor
> OUR COST не выводится ни для какого типа.

### 7.14 Сумма категории и общий итог

- **Сумма в шапке категории:**
  - Client / Contract (init и CO) — показываем `${totalFormatted}`.
  - Internal (init и CO) — показываем отформатированную сумму категории.
  - Subcontractor — суммы категории в шапке **нет** (только название категории).
- **Общий итог «Total Cost» внизу документа:**
  - Показываем в **change order** (client, internal, contract).
  - **Не показываем** во всех `initial_*` и в обоих subcontractor.

---

## 8. Глоссарий — поля payload, участвующие в условиях

Здесь все переменные из payload, от которых зависит отображение (см. раздел 7).
Описания нужно подтвердить/уточнить там, где помечено **(?)**. Значения и наличие
проверены по тестовому `payloads/example03.json` (20 items, есть кастомы всех типов).

### 8.1 Уровень item (`category.subcategories[].items[]`)

| Поле | Тип (в example03) | Где влияет (раздел) | Что это / описание |
|---|---|---|---|
| `catelogId` | строка (`"1-9-1"`, либо `"Custom"`) | 7.2, 7.4, 7.6, 7.7, 7.9, 7.11 | ID позиции в каталоге. Спец-значение **`"Custom"`** = кастомная (ручная) позиция. У каталожных подставляется в заголовок «ITEM {catelogId}.». |
| `omitFromPDF` | bool (`false`) | 7.1 | Флаг «не выводить эту позицию в документ». `true` → item полностью скрыт. |
| `priceHidden` | bool (`true`) | 7.7, 7.8 | «Цена скрыта от клиента». **Действует только на non-CO темплейтах:** при `true` `price`/`total` → `"N/A"` (client → N/A, internal init → приписка «(hidden from customer)»), плюс отключает Maximum refund. **На Change Order игнорируется** — цену не скрываем ни client, ни internal (`hide_prices=False`), приписки на internal CO нет. |
| `priceNotApplicable` | bool (`false`) | — | Присутствует в payload, но в условиях **этих** темплейтов сейчас не используется. **(?) НАДО УТОЧНИТЬ** — назначение поля и влияет ли оно где-то ещё. |
| `quantity` | строка (`"1"`) | 7.6, 7.9 | Количество. Выводится в колонке Quantity у каталожных. **⚠️ Известный баг приложения:** в internal у *кастомных* `quantity` подставляется как «цена» в Catalog Price Description. Это баг на стороне приложения — работаем с ним вынужденно (поведение сохраняем как есть). |
| `price` | строка (`"N/A"` / число) | 7.9 | Каталожная цена за единицу (до зон/скидок). Используется в Catalog Price Description (только internal, только каталожные). |
| `total` | строка (`"42 903,574"`) | 7.6, 7.7 | Итоговая стоимость позиции. Выводится в колонке Total; `"N/A"` при `priceHidden`. Приходит уже как строка — это формат денег США, используем его как есть (не переформатируем). |
| `maxRefundAmount` | число (`36660`) | 7.8 | Максимальная сумма возврата (по incentives на момент подписания). Блок Maximum refund amount. Не показываем, если пусто/`"N/A"`/при `priceHidden`/на change order. |
| `additionalInfo` | строка (часто `""`) | 7.3 | Доп. примечание к позиции (клиентское). У каталожных — под «ADDITIONAL NOTE:», у кастомных — сразу текстом. |
| `longDescription` | строка/HTML (часто `""`) | 7.4 | Подробное клиентское описание. Показывается **только у каталожных**. |
| `internalNotes` | строка | 7.12 | Внутренняя заметка (не для клиента). Блок «INTERNAL NOTES» только в internal. |
| `internalInstructions` | строка | 7.12 | Внутренняя инструкция бригаде. Блок «INTERNAL INSTRUCTIONS» только в internal. Поддерживает `**жирный**`. |
| `photos` | массив (часто `[]`) | 7.5 | Список фото. Если непустой — ссылка «Click here for images». |
| `id` | строка (ObjectId) | 7.5 | ID позиции; подставляется в URL ссылки на фото (`guide_details/{id}`). |
| `name` | строка | 7.2 | Название позиции (в заголовок строки). |
| `customData` | объект (`{}` у каталожных) | 7.2, 7.11 | Данные кастомной позиции (см. 8.2). У каталожных пустой. |

### 8.2 Уровень `item.customData` (только у кастомных items)

| Поле | Значения в example03 | Где влияет | Что это / описание |
|---|---|---|---|
| `itemType` | `default`, `credit`, `note`, **`materials`** | 7.2, 7.11 | Подтип кастома. Шаблон **явно** различает `credit` («Custom Credit item:») и `note` («Custom Note item:», без OUR COST); всё остальное (**включая `materials` и `default`**) → «Custom item:». **(?)** должен ли `materials` отображаться иначе? |
| `subcontractorProposalAmount` | число | 7.11 | OUR COST → «Subcontractor proposal amount». Сумма по предложению субподрядчика. |
| `inHouseTeamCost` | число | 7.11 | OUR COST → «In house team cost». Стоимость работ своей бригады. |
| `materialsAdminCost` | число | 7.11 | OUR COST → выводится как «**Other cost**». **(?)** название поля про материалы/админ, а в выводе «Other cost» — это намеренно? |
| `recommendedCost` | число | 7.11 | OUR COST → «Recommended cost». Рекомендованная цена позиции. |
| `deliveryAndLogisticsCost` | число | — | Есть в payload, но в условиях этих темплейтов **не используется**. **(?)** нужно ли выводить в OUR COST? |
| `pricingNotes` | строка | — | Есть в payload, но в условиях этих темплейтов **не используется**. **(?)** для чего и куда выводить? |

### 8.3 Уровень category / subcategory

| Поле | Где влияет | Что это / описание |
|---|---|---|
| `category.id` | 7.2 (шапка), 7.13 | ID/номер категории — в шапку категории перед названием. |
| `category.name` | шапка категории | Название категории. |
| `category.total` | 7.14 | Сумма по категории. Из неё считается отображаемое значение (см. `totalFormatted`). |
| `category.subcategories[]` | обход (7.1) | Список подкатегорий. |
| `subcategory.name` | шапка подкатегории | Название подкатегории. |
| `subcategory.items[]` | обход (7.1) | Список позиций. |

### 8.4 Уровень корня (`data`) и производные значения

| Поле | Где влияет | Что это / описание |
|---|---|---|
| `estimatesInfo[0].squareFootage` | шапка документа | Площадь проекта (кв. футы). Выводится в шапке (кроме change order и где шапки нет). Также доступна как `sqFt` в формулах `EXP[...]`. |
| `estimatesInfo[0].totalCost` | 7.14 | Общая стоимость сметы — основной источник для общего итога. |
| `category.totalFormatted` | 7.14 | **Производное** (считается перед рендером): `total` категории с разделителями тысяч. Выводится в шапке категории. |
| `grandTotalFormatted` | 7.14 | **Производное**: общий итог `${...}` (из `totalCost`, иначе сумма категорий). Строка «Total Cost» внизу change order. |

> Производные `totalFormatted` и `grandTotalFormatted` в payload **не приходят** — их
> вычисляет препроцессинг (`render.py` / прод-роуты). На стороне JS их нужно будет
> посчитать самостоятельно из `total` / `totalCost`.

### 8.5 Открытые вопросы (ждут уточнения)

1. **`priceNotApplicable`** — назначение поля; влияет ли где-то, кроме этих темплейтов.
2. **`customData.itemType = "materials"`** — должен ли отображаться иначе, чем обычный «Custom item:».
3. **`materialsAdminCost` → «Other cost»** — намеренно ли поле «materials/admin» выводится в OUR COST под подписью «Other cost».
4. **`customData.deliveryAndLogisticsCost`** — нужно ли выводить (например, в OUR COST) и где.
5. **`customData.pricingNotes`** — назначение и куда выводить.
6. **Material item (`itemType = "materials"`) — как должно меняться отображение?**
   Сейчас он не отличается от обычного «Custom item:» (тот же заголовок, тот же
   набор блоков, OUR COST показывается как у default). Нужно уточнить: должен ли
   у material-айтема быть свой заголовок/подпись, особый набор полей в OUR COST
   (например `materialsAdminCost` / `deliveryAndLogisticsCost`), скрываться ли
   какие-то блоки — то есть **чем именно material item должен отличаться** в выводе.

> Решённые ранее: `quantity` у кастомных в Catalog Price Description — известный баг
> приложения, поведение сохраняем; `total` — приходит строкой в формате денег США,
> используем как есть.
