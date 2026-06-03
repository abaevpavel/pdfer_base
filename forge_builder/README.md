# Forge Document Builder — песочница темплейтов

Параллельная dev-площадка для проекта **Forge**. Прод-эндпоинты в `app/`
(`/proposal`, `/change-order`, `/internal-scope`, `/subcontractor-scope`,
`/checklist`) **не трогаются** — здесь только копии для разработки новых вариантов.

## Матрица 2 × 4

| Вариант | Initial proposal | Change order |
|---|---|---|
| **Client** | `initial_client_scope.html` (= прод proposal) | `change_order_client.html` (= прод change order) |
| **Internal** | `initial_internal_scope.html` (= прод internal scope) | `change_order_internal.html` 🆕 |
| **Subcontractor** | `initial_subcontractor_scope.html` (= прод subcontractor) | `change_order_subcontractor.html` 🆕 |
| **Contract** | `initial_contract.html` 🆕 | `change_order_contract.html` 🆕 |

Отличия вариантов:
- **Client** — клиентский вид (цены, колонка Total, grand total).
- **Internal** — + блоки `INTERNAL INSTRUCTIONS` / `INTERNAL NOTES`, фильтр `money`.
- **Subcontractor** — без цен (нет колонки Total и grand total).
- **Contract** — таблицы как у client + плейсхолдер-страницы (cover / terms / signatures),
  помечены `[ PLACEHOLDER ]`, заполняются позже.

## Запуск

```bash
# из папки forge_builder, через venv проекта
../.venv/bin/python render.py <template> [payload]

../.venv/bin/python render.py change_order_internal            # payload по умолчанию example01.json
../.venv/bin/python render.py initial_contract example02.json
../.venv/bin/python render.py --all example02.json             # все 8 темплейтов
../.venv/bin/python render.py                                  # список темплейтов + помощь
```

Результат — в `out/`:
- **HTML всегда** (открыть в браузере = превью темплейта).
- **PDF** — только если в системе есть `wkhtmltopdf` (иначе шаг пропускается с сообщением).
  Установить: `brew install --cask wkhtmltopdf`.

## A4-редизайн (`*_a4.html`)

Параллельно базовым 8 темплейтам (старый landscape) есть набор **`*_a4.html`** —
редизайн под проект Forge: **A4 портрет, синяя палитра**, баннер вплотную к верху,
синий футер «FULL PROJECT SCOPE … Page X / N» на каждой странице, фиксированные
ширины колонок, keep-группы (шапка категории не отрывается от первого item),
разрыв длинных items по странице без маркера.

8 файлов: `initial_{client_scope,internal_scope,subcontractor_scope,contract}_a4.html`
и `change_order_{client,internal,subcontractor,contract}_a4.html`.

Генерируются билд-хелпером `_build_a4_variants.py` из общих кусков, но на выходе —
**самодостаточные** файлы (стиль внутри каждого). Эталон — `initial_client_scope_a4.html`
(правился вручную); остальные 7 — генератором. Перегенерировать:
`../.venv/bin/python _build_a4_variants.py`.

### Превью с разбивкой на A4-страницы

```bash
../.venv/bin/python render.py initial_client_scope_a4 example02.json --paged
```
Флаг `--paged` вшивает [Paged.js](https://pagedjs.org) — браузер раскладывает HTML
по A4-листам с живыми номерами страниц (нужен интернет, грузится с CDN). Это
**приближение**; финальные разрывы даёт wkhtmltopdf. Без `--paged` — одна «простыня».

## Структура

```
forge_builder/
├── render.py              # локальный раннер (Jinja + препроцессинг, без Flask; флаг --paged)
├── _build_a4_variants.py  # генератор 7 A4-вариантов из общих кусков
├── templates/             # базовые 8 + A4-набор 8 = 16 темплейтов
├── payloads/              # тестовые JSON (example01.json, example02.json)
└── out/                   # сгенерированные HTML/PDF (не коммитим)
```

`render.py` повторяет препроцессинг прод-роутов: `EXP[...]EXP`, `priceHidden`→N/A,
`totalFormatted`, markdown `**bold**`, `grandTotalFormatted`, фильтры `linkify` и `money`.
