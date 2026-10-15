# Habit Tracker — трекер полезных привычек

**Habit Tracker** — бэкенд REST API для SPA-приложения по формированию полезных привычек. Курсовой проект Skypro по мотивам идеи из книги Джеймса Клира «Атомные привычки».

Пользователь может создавать привычки по принципу «Я буду **[действие]** в **[время]** в **[месте]**», назначать вознаграждение, выбирать периодичность и получать напоминания в Telegram. Приложение предоставляет API для фронтенда; пользовательский веб-интерфейс в состав проекта не входит.

## Возможности

- Регистрация пользователей и авторизация с помощью JWT (`access` / `refresh`).
- Создание, просмотр, изменение и удаление **собственных** привычек.
- Просмотр **публичных** привычек других пользователей без права их редактирования.
- Пагинация списков привычек через `limit` и `offset`, не более 5 записей за запрос.
- Проверка правил формирования привычек при создании и частичном обновлении (`PATCH`).
- Привязка Telegram-аккаунта через одноразовую ссылку и уведомления по расписанию.
- Асинхронная обработка напоминаний с помощью Celery, Redis и Celery Beat.
- Документация REST API: OpenAPI, Swagger UI и ReDoc.
- Настройки CORS, автоматические тесты и проверка стиля кода.

## Технологии

| Компонент | Технология |
| --- | --- |
| Язык / веб-фреймворк | Python, Django 5.2 LTS |
| REST API | Django REST Framework |
| Авторизация | Simple JWT |
| База данных | PostgreSQL |
| Очередь задач / брокер | Celery, Redis |
| Планировщик | Celery Beat |
| Уведомления | Telegram Bot API |
| Документация | drf-spectacular (OpenAPI / Swagger / ReDoc) |
| Кросс-доменные запросы | django-cors-headers |
| Тесты / покрытие | pytest, pytest-django, pytest-cov |
| Стиль | Ruff |
| Запуск | Docker Compose, Gunicorn |

## Структура проекта

```text
habit-tracker/
├── config/                  # Настройки Django, маршрутизация, Celery
├── users/                   # Пользователи, регистрация, JWT, тесты
├── habits/                  # Привычки, API, бизнес-правила, тесты
├── notifications/           # Telegram, напоминания, фоновые задачи, тесты
├── .github/workflows/       # CI-проверки
├── .env.template            # Пример конфигурации окружения
├── Dockerfile
├── docker-compose.yml
├── manage.py
├── pyproject.toml
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

В приложении `habits` определены привычки и правила их формирования; `users` отвечает за пользователей и авторизацию; `notifications` содержит логику Telegram-привязки, планирования и отправки сообщений.

## Модель привычки и бизнес-правила

У привычки есть владелец (`owner`), место (`place`), время (`time`), действие (`action`), признак приятной привычки (`is_pleasant`), связанная привычка (`related_habit`), периодичность в днях (`periodicity`), вознаграждение (`reward`), длительность в секундах (`duration`) и признак публичности (`is_public`).

Ограничения:

1. Нельзя одновременно заполнить `reward` и `related_habit`.
2. Длительность выполнения — **от 1 до 120 секунд**.
3. В качестве `related_habit` допускается только **приятная** привычка текущего пользователя.
4. Приятная привычка (`is_pleasant=true`) не может иметь `reward` или `related_habit`.
5. Периодичность — **от 1 до 7 дней**; по умолчанию 1 день.

Пользователь не может изменить владельца привычки, получить доступ к чужому приватному объекту или управлять чужой публичной привычкой. Правила проверяются и при создании, и при обновлении.

## Быстрый запуск через Docker Compose

**Предварительно:** установлены Docker Engine и Docker Compose. Для отправки настоящих Telegram-уведомлений нужен бот, созданный через [@BotFather](https://t.me/BotFather).

1. Клонируйте репозиторий и перейдите в каталог проекта:

   ```bash
   git clone https://github.com/ALTSisyphus/habit-tracker.git
   cd habit-tracker
   ```

2. Создайте файл окружения:

   ```bash
   cp .env.template .env
   ```

   Укажите в `.env` собственный `SECRET_KEY`, пароль PostgreSQL, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `TELEGRAM_BOT_TOKEN` и `TELEGRAM_BOT_USERNAME`. Для локального HTTP-запуска не включайте production-режим (`PRODUCTION=False`, если этот параметр присутствует в шаблоне). Не публикуйте `.env` в репозитории.

   Пример генерации ключа:

   ```bash
   python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
   ```

3. Соберите и запустите сервисы:

   ```bash
   docker compose up --build -d
   docker compose ps
   ```

   Compose поднимает `db` (PostgreSQL), `redis`, `web` (Django/Gunicorn), `worker` (Celery), `beat` (планировщик) и `bot` (получение сообщений Telegram). Веб-сервис применяет миграции при запуске.

4. При необходимости создайте администратора:

   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

5. Для просмотра журналов:

   ```bash
   docker compose logs -f web worker beat bot
   ```

Остановка контейнеров без удаления данных PostgreSQL:

```bash
docker compose down
```

> Без настоящего Telegram-токена запуск сервиса `bot` может завершаться ошибкой. Для проверки только API можно запустить основные сервисы отдельно: `docker compose up --build -d db redis web worker beat`.

### Адреса после запуска

| Адрес | Назначение |
| --- | --- |
| `http://localhost:8000/api/docs/` | Swagger UI |
| `http://localhost:8000/api/redoc/` | ReDoc |
| `http://localhost:8000/api/schema/` | OpenAPI-схема |
| `http://localhost:8000/health/` | Проверка доступности приложения |
| `http://localhost:8000/admin/` | Django Admin |

## Локальный запуск без Docker

Потребуются Python, PostgreSQL и Redis. Настройте `DATABASE_URL` и `REDIS_URL` в `.env` под локальные сервисы, затем выполните:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.template .env  # только если .env ещё не создан
python manage.py migrate
python manage.py runserver
```

Для автоматических напоминаний дополнительно запустите в отдельных терминалах с активированным окружением:

```bash
celery -A config worker --loglevel=info
```

```bash
celery -A config beat --loglevel=info
```

```bash
python manage.py run_telegram_bot
```

## API

| Метод | Эндпоинт | Доступ / действие |
| --- | --- | --- |
| `POST` | `/api/auth/register/` | Регистрация |
| `POST` | `/api/auth/token/` | Получение JWT-токенов |
| `POST` | `/api/auth/token/refresh/` | Обновление access-токена |
| `GET` | `/api/habits/` | Список своих привычек |
| `POST` | `/api/habits/` | Создать привычку |
| `GET` | `/api/habits/{id}/` | Получить свою привычку |
| `PUT`, `PATCH` | `/api/habits/{id}/` | Изменить свою привычку |
| `DELETE` | `/api/habits/{id}/` | Удалить свою привычку |
| `GET` | `/api/public-habits/` | Просмотр публичных привычек |
| `POST` | `/api/telegram/link/` | Получение одноразовой ссылки для привязки Telegram |

Для защищённых методов требуется заголовок `Authorization: Bearer <access_token>`.

### Примеры запросов

**Регистрация:**

```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"student","email":"student@example.com","password":"StrongPassword123!"}'
```

**Получение JWT:**

```bash
curl -X POST http://localhost:8000/api/auth/token/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"student","password":"StrongPassword123!"}'
```

**Создание привычки:**

```bash
curl -X POST http://localhost:8000/api/habits/ \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"place":"Дом","time":"08:00:00","action":"Читать книгу","duration":120,"periodicity":1,"reward":"Чашка чая","is_public":true}'
```

**Получение списка с пагинацией:**

```http
GET /api/habits/?limit=5&offset=0
```

Ответ содержит `count`, `next`, `previous` и `results`. Максимальный размер страницы — 5 записей.

## Telegram-напоминания

1. Создайте Telegram-бота через [@BotFather](https://t.me/BotFather).
2. Запишите `TELEGRAM_BOT_TOKEN` и `TELEGRAM_BOT_USERNAME` в `.env`.
3. Авторизуйтесь в API и выполните `POST /api/telegram/link/` с JWT-токеном.
4. Откройте полученную в ответе `deep_link` и нажмите **Start** в личном чате с ботом. Одноразовая ссылка действует **10 минут**.
5. После привязки бот сможет отправлять уведомления о полезных привычках по расписанию.

Celery Beat периодически проверяет, когда нужно напомнить о привычке. Задачи передаются через Redis в Celery Worker; отправки учитываются в базе данных, а ошибки обрабатываются с ограничением числа попыток. Приятные привычки используются как вознаграждения и сами не вызывают отдельные напоминания.

Время напоминаний определяется настройкой `TIME_ZONE` в окружении. Возможна небольшая задержка относительно заданного времени из-за периодичности проверки и работы очереди.

> При сбое между успешной отправкой сообщения в Telegram и записью результата в БД теоретически возможен повтор. Telegram `sendMessage` не предоставляет транзакционную гарантию «ровно один раз».

## Тестирование и качество кода

Для локальной проверки (после установки зависимостей из `requirements-dev.txt`):

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
pytest --cov=. --cov-report=term-missing --cov-fail-under=80
ruff check .
python manage.py spectacular --file schema.yml --validate --fail-on-warn
```

Тесты проверяют регистрацию, JWT, CRUD, разделение прав, валидацию, пагинацию и обработку Telegram-уведомлений. Для внешних вызовов Telegram в автоматических тестах используются имитации ответов API. Часть интеграционных проверок конкурентной обработки требует PostgreSQL, а реальную доставку уведомлений следует проверять отдельно с запущенными Redis, Worker, Beat и ботом.

## Безопасность и настройка окружения

- Все секреты и параметры подключения задаются через `.env`; в Git хранится только `.env.template`.
- Для публикации на сервере используйте `DEBUG=False`, надёжный `SECRET_KEY`, отдельные значения `ALLOWED_HOSTS` и `CORS_ALLOWED_ORIGINS`, HTTPS и безопасные пароли БД.
- В production должны работать PostgreSQL и Redis; SQLite используется только для локальных тестов, где это предусмотрено тестовой конфигурацией.
- Telegram-привязка выполняется через одноразовый код, а не через произвольный `chat_id` в запросе.
- Приложение предназначено для использования с SPA-клиентом; сам фронтенд в курсовую работу не входит.