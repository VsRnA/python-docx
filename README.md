# Document Management Service

Monorepo внутреннего сервиса обработки документов.

## Структура

```text
backend/   FastAPI, слоистая архитектура
frontend/  React, TypeScript, Feature Sliced Design
renderer/  WeasyPrint 68 для HTML и PDF
gotenberg  LibreOffice-конвертация исходного DOCX в визуальный PDF
```

Backend разделен на слои:

- `domain` — сущности, value objects и бизнес-правила;
- `application` — use cases и порты;
- `infrastructure` — PostgreSQL, Timeweb S3, GPT Astra 6, Yandex GPT и очередь;
- `presentation` — HTTP API и DTO.

Frontend использует слои FSD:

- `app` — инициализация приложения;
- `pages` — страницы маршрутов;
- `widgets` — крупные композиционные блоки;
- `features` — пользовательские действия;
- `entities` — бизнес-сущности;
- `shared` — UI kit, API client, конфигурация и утилиты.

Документация:

- [`docs/TECHNICAL_SPECIFICATION.md`](docs/TECHNICAL_SPECIFICATION.md) — полное техническое задание;
- [`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md) — этапы, состояние и критерии готовности.

## Локальный запуск backend

```bash
cd backend
uv sync --extra dev
uv run uvicorn document_service.main:app --reload
```

## Локальный запуск frontend

```bash
cd frontend
npm install
npm run dev
```

## Проверки

```bash
cd backend && uv run pytest
cd frontend && npm run typecheck && npm run test
```

## Пакет первоначального разбора

Worker отправляет в GPT Astra 6 четыре явно разделенных типа входов:

- исходный `SOURCE_DOCUMENT.docx` как источник текста и структуры;
- автоматически собранный `SOURCE_RENDER.pdf` как источник страниц, изображений и якорных
  элементов;
- `backend/reference/style-reference.pdf` как детальный визуальный эталон;
- `backend/reference/overview/contact-*.jpg` как обзор всей системы страниц эталона.

Контент из эталона запрещено переносить в результат. Его назначение — только визуальная система,
типографика, шапки, подвалы, предупреждения, таблицы и оформление иллюстраций. Суммарный размер трех
файловых входов контролируется переменной `MAX_AI_FILE_INPUT_BYTES` и по умолчанию равен 50 МБ.

Текущие версии преобразования — `docx-to-html/v2` и `villartec-manual-a4@1.0`. План доведения
до golden test описан в
[`docs/A4_RENDERING_IMPLEMENTATION_PLAN.md`](docs/A4_RENDERING_IMPLEMENTATION_PLAN.md).

До завершения реализации проект намеренно не запускается. Первый полный запуск, миграции и
проверки выполняются в Docker после готовности всех модулей.
# python-docx
