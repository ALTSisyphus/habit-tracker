# Habit Tracker — курсовой проект Skypro

Бэкенд SPA-приложения «Трекер полезных привычек»: Django REST Framework, JWT,
PostgreSQL, Redis, Celery, Telegram Bot API и OpenAPI/Swagger.

Проект рассчитан на Ubuntu 26.04 LTS и VSCode. Рекомендуемая версия Python:
**3.12–3.14**; Docker использует Python 3.12. Django 5.2 — LTS (поддержка Python 3.14 начиная с 5.2.8).
Ubuntu 26.04 поставляет Python 3.14; для локального venv установите
`python3-venv`. Фактическая среда аудита и ограничения указаны в
[CODE_REVIEW_REPORT.md](CODE_REVIEW_REPORT.md).

## Возможности

- Регистрация, JWT access/refresh токены.
- CRUD только собственных привычек; чужие объекты скрыты.
- Публичный список доступен для GET всем (без редактирования).
- Пагинация limit/offset: **не более пяти привычек**.
- Валидация всех пяти обязательных условий, в том числе на `PATCH`.
- Telegram: безопасная привязка через одноразовую ссылку, сообщения по расписанию.
- Celery Beat + Redis + Celery Worker, запись попыток отправки в БД.
- CORS из `.env`, Swagger / ReDoc, тесты pytest.

## Быстрый запуск в Docker (рекомендуется)

1. Установите Docker Engine и Docker Compose plugin.
2. Создайте `.env` на основе шаблона:

   ```bash
   cp .env.template .env
   ```

3. В `.env` **обязательно** задайте случайный `SECRET_KEY` (например,
   `python -c 'import secrets; print(secrets.token_urlsafe(48))'`), реальные
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, безопасный пароль БД и ваши
   `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`. Токен бота получают через
   [@BotFather](https://t.me/BotFather). Имя бота указывается без `@`.
   Если бот не нужен для локального тестирования API, сервис `bot` можно
   не запускать, но Celery и API продолжат работать.

4. Запустите контейнеры (веб-приложение автоматически применяет миграции):

   ```bash
   docker compose up --build -d
   docker compose ps
   ```

5. Откройте:
   - Swagger: <http://localhost:8000/api/docs/>
   - ReDoc: <http://localhost:8000/api/redoc/>
   - Health: <http://localhost:8000/health/>

6. Для администратора:

   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

Docker Compose пробрасывает PostgreSQL, Redis и API **только на 127.0.0.1**;
при публикации в сети используйте HTTPS и reverse proxy (Nginx/Caddy).

### Локальный запуск без Docker

Установите Python 3.12+, PostgreSQL и Redis. Создайте БД и пользователя в
соответствии с `DATABASE_URL` в `.env`. В терминале VSCode:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.template .env  # если ранее ещё не создавали
python manage.py migrate
python manage.py runserver
```

В трёх других терминалах (с активированной `.venv`):

```bash
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info
python manage.py run_telegram_bot
```

В VSCode используйте `Python: Select Interpreter` -> `.venv/bin/python`.

## Работа с API

### Регистрация и токены

```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"student","password":"StrongPassword123!","email":"example@test.ru"}'

curl -X POST http://localhost:8000/api/auth/token/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"student","password":"StrongPassword123!"}'
```

Возьмите поле `access` из ответа. Далее передавайте:
`Authorization: Bearer <access>`.

### Создание полезной привычки

```bash
curl -X POST http://localhost:8000/api/habits/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"place":"Дом","time":"08:00:00","action":"Читать книгу","duration":120,"periodicity":1,"reward":"Чашка кофе","is_public":true}'
```

- `duration`: целое число 1–120, секунды.
- `periodicity`: целое число 1–7, дни, по умолчанию 1.
- `reward` и `related_habit` нельзя указывать одновременно.
- Связанная привычка — **собственная** приятная (`is_pleasant=true`).
- У приятной привычки не может быть `reward` и `related_habit`.
- Указывать `owner` нельзя: он определяется по access-токену.
- Приятные привычки используются как вознаграждение и сами не рассылаются.

### Эндпоинты

| Метод | URL | Доступ |
| --- | --- | --- |
| POST | `/api/auth/register/` | Все |
| POST | `/api/auth/token/` | Все |
| POST | `/api/auth/token/refresh/` | Все |
| GET | `/api/habits/?limit=5&offset=0` | Авторизованный владелец |
| POST | `/api/habits/` | Авторизованный владелец |
| GET | `/api/habits/{id}/` | Владелец |
| PUT, PATCH | `/api/habits/{id}/` | Владелец |
| DELETE | `/api/habits/{id}/` | Владелец |
| GET | `/api/public-habits/` | Все (только чтение) |
| POST | `/api/telegram/link/` | Авторизованный пользователь |
| GET | `/api/schema/` | Все |
| GET | `/api/docs/` | Все |
| GET | `/api/redoc/` | Все |
| GET | `/health/` | Все |

Пример пагинации:

```json
{
  "count": 12,
  "next": "http://localhost:8000/api/habits/?limit=5&offset=5",
  "previous": null,
  "results": []
}
```

Значение `results` в реальном ответе содержит до пяти объектов.

## Подключение Telegram

1. Создайте бота у [@BotFather](https://t.me/BotFather).
2. Добавьте токен и username в `.env`, перезапустите контейнеры.
3. Получите JWT, выполните `POST /api/telegram/link/` с заголовком Bearer.
4. API вернёт `deep_link`, действительный 10 минут. Перейдите по ссылке и
   нажмите **Start** в личном диалоге с ботом.
5. После подтверждения бот начнёт получать право отправлять напоминания.

Никогда не принимайте `telegram_chat_id` от незаверенного клиента. В этом
проекте он сохраняется только после предъявления одноразового кода в Telegram.
Для безопасной работы запускайте **ровно один** экземпляр `bot` с `getUpdates`;
при активном Telegram webhook polling не работает.

Сервис `beat` проверяет расписание раз в минуту. При необходимости задача
сохраняется в таблице `Reminder` с уникальным ключом по привычке и времени,
затем через `worker` передаётся Telegram API. Отправка может задержаться до
минуты. По часам используется `TIME_ZONE` из `.env`.

**Ограничение:** Telegram API не обеспечивает транзакционную доставку и не
принимает ключ идемпотентности. При аварии воркера после доставки, но до
обновления БД, возможно повторное сообщение. Применён подход best-effort:
атомарный захват задачи, журнал отправок, ограничение попыток и восстановление
зависших отправок через 5 минут. Это минимизирует, но не исключает повторы.

## Проверка тестов, стиля и миграций

Установите dev-зависимости и запустите:

```bash
pytest --cov=. --cov-report=term-missing --cov-fail-under=80
ruff check .
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py spectacular --file /tmp/schema.yml --validate --fail-on-warn
```

Тесты используют `config.settings_test` и SQLite в памяти; для тестов не нужен
запущенный PostgreSQL/Redis или настоящий Telegram-токен. API и Celery тестируются
с помощью mock-объектов; реальную рассылку нужно дополнительно проверить с
личным ботом.

## Безопасность и развёртывание

- Настоящий `.env` исключён из Git и из Docker build context.
- Для production установите `DEBUG=False`, надёжный `SECRET_KEY`, разрешённые
  hosts/origins, HTTPS и пароль PostgreSQL, отличный от примера.
- Для production включите `PRODUCTION=True`: HTTPS redirect, защищённые cookie
  и HSTS включаются автоматически; слабый ключ, DEBUG, wildcard hosts и SQLite
  блокируют запуск. Нужен ключ длиной от 50 символов.
- Если HTTPS завершается на доверенном reverse proxy, включите
  `TRUST_PROXY_HTTPS=True` только после настройки удаления и перезаписи
  заголовка `X-Forwarded-Proto` на прокси. Health endpoint исключён из redirect
  для внутренней проверки контейнера. HSTS распространяется на поддомены:
  все поддомены также должны поддерживать HTTPS.
- Статика Django admin обслуживается WhiteNoise после `collectstatic`;
  Docker выполняет эту команду при сборке. Настройте мониторинг и backups.
- При масштабировании Celery Beat должен быть в единственном экземпляре.
- Привязку бота выполняйте только в приватном чате. Дубликаты `chat_id`
  блокируются уникальным ограничением.

## Интеграционные проверки

CI настроен на Python 3.12 и 3.14 с PostgreSQL 16 и Redis 7. Для проверки
локальной тестовой PostgreSQL-базы задайте `TEST_DATABASE_URL` и запустите pytest.
Пользователю БД нужно право создания тестовой базы. Без этой переменной
используется SQLite; тест конкурентной доставки требует PostgreSQL и пропускается.
Запуск workflow в GitHub не считается подтверждённым локальным аудитом.

`READ_DOT_ENV=False` отключает чтение `.env` для изолированных проверок.
Значения пароля в `DATABASE_URL` должны быть URL-encoded, если содержат `@`,
`/`, `:`, `#` или другие специальные символы. Это относится и к паролю,
интерполируемому Docker Compose в URL; используйте URL-safe случайный пароль.
Не сохраняйте вывод `docker compose config` с реальными секретами в отчётах.
