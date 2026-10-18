# Document Management Service

Веб-сервис принимает DOCX, формирует редактируемый HTML через GPT Astra 6, хранит версии и изображения, поддерживает AI-правки, перевод и HTML-публикации.

## Состав

- `backend` — FastAPI, PostgreSQL, очередь задач в PostgreSQL, Timeweb S3, GPT Astra 6 и YandexGPT.
- `frontend` — React/TypeScript-интерфейс документов, редактора и стилизаций.
- merge-документы отправляются в GPT Astra 6 вместе с исходными DOCX и PDF-образцом стиля.

Первичный импорт отправляет в Astra исходный DOCX, PDF-образец стилизации, изображения из DOCX и prompt выбранной стилизации. Prompt стилизации хранится в базе данных. Для слияния документов Astra получает исходные DOCX, промпт слияния и тот же PDF-образец стилизации.

## Запуск

```bash
cp backend/.env.example backend/.env
docker compose build
docker compose up -d
docker compose ps
```

API: `http://localhost:8000`
Frontend: `http://localhost:8080`

Миграции выполняются контейнером `migrate`. Остановка без удаления данных:

```bash
docker compose down
```

## Локальные проверки

```bash
cd backend
python -m compileall -q src tests
python scripts/check_import_boundaries.py
pytest

cd ../frontend
npm ci
npm run typecheck
npm run check:boundaries
npm run lint
npm run build
```

## Архитектура

Backend разделён на `domain`, `application`, `infrastructure` и `presentation`. Frontend использует слои `app`, `pages`, `widgets`, `features`, `entities` и `shared`.

Результат обработки — безопасный канонический HTML с `data-block-id` и ссылками `asset://UUID`. HTML можно редактировать в интерфейсе и публиковать с материализованными изображениями. PDF-экспорт и отдельный Chromium-renderer в текущем продукте не используются.

Основные материалы стилизации:

- prompt выбранной опубликованной версии хранится в PostgreSQL;
- PDF-образец выбранной опубликованной версии хранится в S3;
- ответы Astra проверяются кодовыми Pydantic- и HTML-контрактами;
- JSON-контракт настроек: `docs/contracts/style-settings.v1.json`.
