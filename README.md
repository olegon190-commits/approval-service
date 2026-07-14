# approval-service

Сервис согласования контента перед публикацией. Принимает заявки на согласование, фиксирует решения (approve / reject / cancel), ведёт аудит-лог и готовит события для интеграций.

## Быстрый старт

### Вариант 1 — Docker (Postgres)

```bash
docker-compose up --build
```

Сервис поднимется на `http://localhost:8000`, база — Postgres 16.

### Вариант 2 — локально (SQLite)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

По умолчанию используется SQLite (`approval.db`), таблицы создаются автоматически. Для Postgres задайте `DATABASE_URL`:

```bash
export DATABASE_URL=postgresql://approval:approval@localhost:5432/approval
```

SQL-миграции лежат в `migrations/`.

## Тесты

```bash
python -m pytest tests/ -v
```

17 тестов: создание, идемпотентность, изоляция workspace, решения, неизменность финального статуса, права доступа.

## Auth (заглушка)

Запросы авторизуются через заголовки:

| Заголовок | Значение | Пример |
|---|---|---|
| `X-User-Id` | идентификатор пользователя | `usr_1` |
| `X-Workspace-Id` | workspace пользователя | `ws_1` |
| `X-Actions` | разрешённые действия через запятую | `approval:read,approval:create` |

Действия: `approval:read`, `approval:create`, `approval:decide`, `approval:cancel`.

В реальной системе заголовки заменяются JWT/OAuth middleware — интерфейс (user, workspace, actions) остаётся тем же.

## API

```
GET  /health
GET  /ready
POST /api/v1/workspaces/{workspace_id}/approval-requests
GET  /api/v1/workspaces/{workspace_id}/approval-requests
GET  /api/v1/workspaces/{workspace_id}/approval-requests/{request_id}
POST /api/v1/workspaces/{workspace_id}/approval-requests/{request_id}/approve
POST /api/v1/workspaces/{workspace_id}/approval-requests/{request_id}/reject
POST /api/v1/workspaces/{workspace_id}/approval-requests/{request_id}/cancel
```

Интерактивная документация: `http://localhost:8000/docs`

### Пример: создать заявку

```bash
curl -X POST http://localhost:8000/api/v1/workspaces/ws_1/approval-requests \
  -H "Content-Type: application/json" \
  -H "X-User-Id: usr_1" \
  -H "X-Workspace-Id: ws_1" \
  -H "X-Actions: approval:create" \
  -H "Idempotency-Key: my-unique-key-1" \
  -d '{
    "sourceType": "publication",
    "sourceId": "pub_123",
    "title": "Instagram reel draft",
    "description": "Needs final approval",
    "reviewerUserIds": ["usr_1", "usr_2"]
  }'
```

### Пример: согласовать

```bash
curl -X POST http://localhost:8000/api/v1/workspaces/ws_1/approval-requests/{id}/approve \
  -H "Content-Type: application/json" \
  -H "X-User-Id: usr_2" \
  -H "X-Workspace-Id: ws_1" \
  -H "X-Actions: approval:decide" \
  -d '{"comment": "Approved"}'
```

## Идемпотентность

Передайте заголовок `Idempotency-Key` при создании заявки — повтор запроса с тем же ключом вернёт существующую заявку вместо создания дубля.

Подробнее об архитектуре — в [DESIGN.md](DESIGN.md).
