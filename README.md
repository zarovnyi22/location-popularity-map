# Мапа популярності локацій

REST API для сервісу, де люди додають місця, пишуть відгуки з оцінкою 1–5,
ставлять лайки/дизлайки, а бекенд сам рахує рейтинг і популярність
(без збережених колонок у БД). Координати є в моделі — мапу на фронті
можна намалювати з lat/lng; цей репозиторій лише API.

## Стек

Django 5 · DRF · PostgreSQL · Redis · django-filter · session auth (без JWT) · Docker Compose

## Запуск

**Docker (основний шлях):**

```bash
cp .env.example .env
docker compose up --build
```

API: `http://localhost:8000/api/`  
Адмінка: `http://localhost:8000/admin/`  
(`docker compose exec web python manage.py createsuperuser`)

**Локально без Docker** (sqlite, швидка перевірка):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
echo "USE_SQLITE=1" >> .env
python manage.py migrate
python manage.py runserver
```

`.env` підхоплюється через `python-dotenv`. Якщо Redis немає — кеш і
ліміт переглядів йдуть через `LocMemCache`, логіка та сама.

## Тести

```bash
python manage.py test
```

Під час тестів автоматично sqlite + LocMemCache (`TESTING` у settings).

## Структура

```
config/          settings, urls
apps/accounts/   реєстрація, логін/логаут, скидання пароля
apps/locations/  категорії, локації, soft delete, перегляди, кеш, експорт
apps/reviews/    відгуки, голоси, листи, підписки
```

## API коротко

### Auth — `/api/auth/`

| | |
|---|---|
| `POST register/` | реєстрація |
| `POST login/` | сесія + cookie |
| `POST logout/` | вихід |
| `GET me/` | поточний юзер |
| `POST password-reset/` | лист зі скиданням |
| `POST password-reset/confirm/` | `uid`, `token`, `new_password` |

### Категорії — `/api/categories/`

CRUD. Читати можуть усі, писати — лише staff.

### Локації — `/api/locations/`

| | |
|---|---|
| `GET /` | `?search=`, `?category=`, `?rating_min=`, `?rating_max=`, `?author=`, `?ordering=created_at\|-rating\|-popularity` |
| `POST /` | створити (auth) |
| `GET /{id}/` | деталі + перегляд (макс. 1/год на юзера чи сесію) |
| `PATCH\|PUT /{id}/` | автор або адмін |
| `DELETE /{id}/` | soft delete |
| `POST /{id}/subscribe/` · `unsubscribe/` | бонус: листи про нові відгуки |
| `GET /export/?format=json\|csv&scope=filtered\|all` | експорт (pandas для CSV) |

У відповіді локації завжди є обчислені поля: `rating`, `reviews_count`,
`views_7d`, `popularity`.

`scope=filtered` (дефолт) — ті самі фільтри, що й у списку.
`scope=all` — усі невидалені локації, фільтри ігноруються.

### Відгуки

| | |
|---|---|
| `GET\|POST /api/locations/{id}/reviews/` | список / створити |
| `GET\|PATCH\|DELETE /api/reviews/{id}/` | автор або адмін |
| `POST /api/reviews/{id}/vote/` | `{"vote_type": "like"\|"dislike"}` |
| `DELETE /api/reviews/{id}/vote/` | зняти голос |

Один відгук на локацію від юзера, один голос на відгук (можна змінити like↔dislike).

## CSRF (session auth)

На `POST`/`PUT`/`PATCH`/`DELETE` потрібен CSRF:

1. Зробити будь-який `GET` — прийде cookie `csrftoken`
2. Відправити його в заголовку `X-CSRFToken`
3. Запити з `credentials: "include"` / `withCredentials: true`

## Популярність

```
popularity = rating * 2 + reviews_count * 1.5 + views_7d * 0.5
```

Ваги можна змінити через `POPULARITY_*_WEIGHT` у `.env`.
Рахунок у `apps/locations/services.py::annotate_rating_and_popularity` —
на кожен запит через ORM, у моделі цих полів немає.

## Як влаштовано (коротко)

Рейтинг і популярність свідомо не денормалізував: у ТЗ прямо «не зберігати
в БД», тож Avg/Count/ExpressionWrapper на queryset. Кеш списку локацій —
не `cache.clear()`, а version key у Redis: змінили локацію/відгук → bump
версії, старі ключі просто перестають попадати. Перегляди пишуться в
`LocationView`, а «раз на годину» тримає `cache.add` (атомарний lock).
Email після нового відгуку йде з сигналу синхронно — для тестового ок,
на проді я б виніс у чергу. Soft delete через окремий manager, щоб випадково
не світити видалені в API.
