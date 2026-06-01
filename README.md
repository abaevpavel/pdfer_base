# pdfer_base — PDF Generation Service

Flask-сервис для генерации PDF-документов по данным смет. Принимает JSON от iOS-приложения EstimatingTool и возвращает ссылки на готовые PDF.

Задеплоен на Render: `pdfer-base.onrender.com`

---

## Стек

| Компонент | Версия / описание |
|-----------|-------------------|
| Python 3 | основной язык |
| Flask | HTTP-сервер |
| Jinja2 | шаблонизатор HTML |
| pdfkit + wkhtmltopdf | HTML → PDF |
| Gunicorn | production WSGI |
| Docker (Ubuntu 20.04) | контейнер для деплоя |
| schedule | очистка статики раз в сутки |

---

## Запуск

### Docker (production)
```bash
docker build -t pdfer .
docker run -p 80:80 -e ROOT_URL=https://pdfer-base.onrender.com pdfer
```

### Локально (без wkhtmltopdf)
wkhtmltopdf не устанавливается через Homebrew на macOS. Для локального просмотра шаблонов используется скрипт рендера в HTML:

```bash
python3 /tmp/render_templates.py proposal change_order internal_scope subcontractor
```

Скрипт берёт тестовый payload из `/tmp/test_payload_full.json`, рендерит каждый шаблон через Jinja2 и открывает HTML в браузере.

---

## Структура

```
pdfer_base/
├── Dockerfile
├── app/
│   ├── main.py              # Flask app, регистрация роутов
│   ├── proposal.py          # POST /proposal
│   ├── change_order.py      # POST /change-order
│   ├── internal_scope.py    # POST /internal-scope
│   ├── checklist.py         # POST /checklist
│   ├── subcontractor.py     # POST /subcontractor-scope
│   └── templates/
│       ├── proposal.html
│       ├── change_order.html
│       ├── internalScope.html
│       ├── checklist.html
│       └── subcontractor.html
```

---

## Эндпоинты

| Метод | Путь | Возвращает |
|-------|------|------------|
| POST | `/proposal` | `{ proposal: "<url>.pdf" }` |
| POST | `/change-order` | `{ change_order: "<url>.pdf" }` |
| POST | `/internal-scope` | `{ internal_scope: "<url>.pdf" }` |
| POST | `/subcontractor-scope` | `{ subcontractor_scope: "<url>.pdf" }` |
| POST | `/checklist` | `{ body: "<html string>" }` |
| GET | `/check` | `"CHECK WORKING"` |

PDF-файлы сохраняются в `./static/<type>_<timestamp>.pdf` и очищаются ежедневно в 01:00.

---

## Поток генерации PDF

1. Принять JSON-тело запроса
2. Предобработать данные:
   - вычислить формулы `EXP[...]EXP`
   - преобразовать URL в кликабельные ссылки (`linkify`)
   - выставить `price = "N/A"` / `total = "N/A"` для `priceHidden: true`
   - отформатировать `totalFormatted` для категорий
3. Рендер Jinja2-шаблона → HTML-строка
4. `pdfkit.from_string(html, path)` → PDF-файл
5. Вернуть `{ ключ: ROOT_URL + "/static/файл.pdf" }`

---

## Конфигурация

| Переменная | Дефолт | Описание |
|------------|--------|----------|
| `ROOT_URL` | `http://localhost` | База URL для ссылок на PDF |

---

## Структура входного JSON

```json
{
  "estimatesInfo": [{
    "squareFootage": 348,
    "totalCost": 45000,
    "estimateDate": "2024-01-15",
    "author": "John Doe"
  }],
  "clientInfo": [{
    "clientFirst": "Aaron",
    "clientLast": "Smith",
    "clientStreet": "123 Main St",
    "city": "Upper Marlboro",
    "state": "MD",
    "zip": "20774",
    "pricingZone": "MD,VA"
  }],
  "categories": [{
    "id": "CAT-1",
    "name": "Framing",
    "total": 5000,
    "subcategories": [{
      "name": "Interior Framing",
      "total": 5000,
      "items": [{
        "catelogId": "FR-001",
        "name": "Interior Wall Framing",
        "price": 12.50,
        "total": 5000,
        "quantity": 400,
        "longDescription": "<p>HTML string, client-facing</p>",
        "additionalInfo": "Extra note for client",
        "internalNotes": "Internal only",
        "internalInstructions": "Internal only",
        "priceHidden": false,
        "priceNotApplicable": false,
        "omitFromPDF": false,
        "hasCustomPricing": false,
        "maxRefundAmount": "500",
        "photos": ["https://..."],
        "trades": [{ "name": "Framer", "image": "..." }],
        "zoneMultiplier": 1.0,
        "zoneAdjustedPrice": 12.50
      }]
    }]
  }]
}
```

### Кастомные айтемы (`catelogId == "Custom"`)

Имеют `hasCustomPricing: true` и дополнительное поле `customData`:

```json
{
  "catelogId": "Custom",
  "hasCustomPricing": true,
  "customData": {
    "itemType": "default | credit | note",
    "recommendedCost": 4200,
    "subcontractorProposalAmount": 3500,
    "inHouseTeamCost": 3000,
    "materialsAdminCost": 700,
    "pricingNotes": "..."
  }
}
```

- `itemType: "default"` — обычный кастомный айтем с ценой
- `itemType: "credit"` — кредит/скидка (custom credit item)
- `itemType: "note"` — информационная заметка без цены

---

## Специальный синтаксис в шаблонах

### `EXP[выражение]EXP`

Python-выражение, вычисляемое при рендере. Доступны переменные:
- `sqFt` — `estimatesInfo[0].squareFootage`
- `math` — модуль `math`

Пример: `EXP[sqFt * 2.5]EXP` → `870`

### `**текст**` → `<b>текст</b>`

Markdown-жирный в полях `internalNotes` и `internalInstructions` (только в internalScope).

### Jinja-фильтр `linkify`

Преобразует голые URL в кликабельные ссылки вида `<a href="...">domain - View Link</a>`.

### Jinja-фильтр `money` (только internalScope)

Форматирует числа: `4200` → `$4,200.00`.

---

## Шаблоны

### `proposal.html` — клиентский пропосал

Документ для клиента. Содержит:
- Заголовок: `ATTACHMENT 1: FULL PROJECT SCOPE.`
- Подзаголовок: `BASEMENT TOTAL SQ. FT. = X SQ. FT.`
- Предупреждение о септике
- Таблицы по категориям (красный хедер) → подкатегориям (синий хедер) → айтемам
- Колонки: Description + Quantity + Total
- Footer каждого айтема: разделитель + Maximum refund amount (если есть) + Unit pricing disclaimer

### `change_order.html` — изменение к контракту

Аналог proposal с отличиями:
- Показывает Grand Total по всему документу
- Footer айтема: только разделитель + Unit pricing disclaimer (без Max refund)

### `internalScope.html` — внутренний scope

Документ для команды. Дополнительно показывает:
- `internalNotes` и `internalInstructions` для каждого айтема
- Секцию с детальным разбором кастомных айтемов (стоимость субподрядчика, in-house, материалы)
- Footer айтема: разделитель + Catalog Price Description + Maximum refund amount + Unit pricing disclaimer
- Фильтр `money` для форматирования цен

### `checklist.html` — чеклист

Не PDF, возвращает HTML-строку. Рендерит `todo_list_sections` с задачами, подзадачами и фото.

### `subcontractor.html` — scope для субподрядчика

Упрощённый вариант proposal:
- Заголовок: `ATTACHMENT 1: SUBCONTRACTOR SCOPE.`
- Подзаголовок: `PROJECT TOTAL SQ. FT. = X SQ. FT.`
- Только колонки Description + Quantity (без Total)
- Нет колонки цен и footer с pricing notes
- Кастомные айтемы показываются как в proposal

---

## Footer айтема — детали стилизации

Все три элемента footer используются в виде Jinja-макросов.

**Разделитель** (`pricing_separator`) — чёрная линия из подчёркиваний.

**Maximum refund amount** (`maximum_refund_amount`) — красный заголовок и значение, описание чёрным курсивом на той же строке (через `<br/>`). Показывается если `item.maxRefundAmount` задан и не `N/A`.

**Unit pricing disclaimer** (`unit_pricing_disclaimer`) — "Unit pricing" жирным красным, остальной текст чёрным курсивом.

**Catalog Price Description** (`catalog_price_description`, только internalScope) — красный заголовок + значение через `money`-фильтр, описание чёрным курсивом на той же строке.

---

## Деплой

Сервис задеплоен на Render.com. При пуше в `main` Render автоматически пересобирает Docker-образ и перезапускает контейнер.

Dockerfile устанавливает `wkhtmltopdf 0.12.6` из `.deb`-пакета — это единственный способ получить рабочий бинарник в Ubuntu 20.04.
