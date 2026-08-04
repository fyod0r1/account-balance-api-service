# Account Balance API Service

Асинхронный REST API для пользователей, администраторов, счетов и платежных webhook-пополнений.

Стек:

- FastAPI как допустимая альтернатива Sanic;
- PostgreSQL;
- SQLAlchemy async ORM;
- Alembic;
- Docker Compose.

## Запуск через Docker Compose

```bash
docker compose up --build
```

Приложение будет доступно на `http://localhost:8000`.

Swagger UI:

```text
http://localhost:8000/docs
```

## Запуск без Docker Compose

Нужен Python 3.12+ и запущенный PostgreSQL.

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

По умолчанию `.env.example` ожидает базу:

```text
postgresql+asyncpg://account_balance:account_balance@localhost:5432/account_balance
```

## Тестовые учетные записи

Пользователь:

```text
email: user@example.com
password: userpass123
```

Администратор:

```text
email: admin@example.com
password: adminpass123
```

## Основные endpoints

Авторизация:

```http
POST /api/v1/auth/login
```

Пользователь:

```http
GET /api/v1/me
GET /api/v1/me/accounts
GET /api/v1/me/payments
```

Администратор:

```http
POST /api/v1/admin/users
GET /api/v1/admin/users
PATCH /api/v1/admin/users/{user_id}
DELETE /api/v1/admin/users/{user_id}
```

Webhook платежной системы:

```http
POST /api/v1/payments/webhook
```

## Подпись webhook

Подпись считается через SHA-256 от строки:

```text
{account_id}{amount}{transaction_id}{user_id}{secret_key}
```

Значения идут в алфавитном порядке ключей без поля `signature`.

Пример для `PAYMENT_WEBHOOK_SECRET=gfdmhghif38yrf9ew0jkf32`:

```json
{
  "transaction_id": "5eae174f-7cd0-472c-bd36-35660f00132b",
  "user_id": 1,
  "account_id": 1,
  "amount": 100,
  "signature": "7b47e41efe564a062029da3367bde8844bea0fb049f894687cee5d57f2858bc8"
}
```

Webhook идемпотентен по `transaction_id`: повторный запрос с тем же `transaction_id`
не пополняет баланс второй раз.

## Проверки

Быстрые unit/API tests без внешних сервисов:

```bash
python -m pytest -q
```

Статические проверки:

```bash
python -m ruff check .
python -m ruff format --check .
```

PostgreSQL integration tests требуют запущенный `postgres` из Docker Compose:

```bash
$env:RUN_INTEGRATION_TESTS = "1"
$env:TEST_DATABASE_URL = "postgresql+asyncpg://account_balance:account_balance@localhost:5432/account_balance"
python -m pytest -q -m integration
```

API e2e tests требуют запущенное приложение:

```bash
$env:RUN_E2E_TESTS = "1"
$env:E2E_API_URL = "http://localhost:8000"
python -m pytest -q -m "e2e and not browser"
```

Browser e2e tests требуют Playwright browser runtime:

```bash
python -m playwright install chromium
$env:RUN_BROWSER_E2E_TESTS = "1"
$env:E2E_API_URL = "http://localhost:8000"
python -m pytest -q -m browser
```
