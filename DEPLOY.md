# Wdrożenie produkcyjne

Produkcyjny stack składa się z PostgreSQL, API, osobnego workera i Caddy z automatycznym HTTPS. API wykonuje migracje Alembic przed startem, a worker czeka na gotowość API i bazy.

## Pierwsze uruchomienie

1. Skieruj rekord DNS domeny na VPS i zainstaluj Docker Compose v2.
2. Sklonuj `main`, skopiuj `.env.example` do `.env` i ustaw wszystkie wymagane sekrety.
3. Uruchom stack:

```bash
DOMAIN=app.example.com docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
curl -fsS https://app.example.com/api/health/ready
```

W produkcji wymagane są `PUBLIC_BASE_URL`, `ADMIN_API_KEY`, `POSTGRES_PASSWORD`, dane Resend, oba klucze Turnstile oraz co najmniej jeden serwerowy klucz LLM. `AUTH_REQUIRED=true` i `COOKIE_SECURE=true` są wymuszane przez Compose. Kluczy LLM nie podaje się w UI.

## Aktualizacja

```bash
./scripts/backup_postgres.sh
git pull --ff-only origin main
DOMAIN=app.example.com docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
curl -fsS https://app.example.com/api/health/ready
```

Przed przełączeniem głównej domeny wdrażaj tę samą wersję na tymczasowej subdomenie. Ręczny smoke test powinien objąć: rejestrację, e-mail weryfikacyjny, logowanie, prawdziwy film YouTube, upload, pytanie, usunięcie źródła, retry oraz przekroczenie limitu.

## Backup i odtworzenie

`scripts/backup_postgres.sh` wykonuje skompresowany `pg_dump`; domyślnie zapisuje do `./backups` i usuwa pliki starsze niż 14 dni. Ustaw cron poza repozytorium, np. codziennie o 02:15. Kopie należy przesyłać także poza VPS.

```bash
BACKUP_DIR=/srv/backups BACKUP_RETENTION_DAYS=14 ./scripts/backup_postgres.sh
./scripts/restore_postgres.sh /srv/backups/video-analizier-YYYYmmddTHHMMSSZ.sql.gz
```

Odtworzenie jest operacją destrukcyjną i wymaga wpisania `RESTORE`. Najpierw zatrzymaj `api` i `worker`; po odtworzeniu uruchom `alembic upgrade head` przez ponowne uruchomienie API.

## Diagnostyka

```bash
docker compose -f docker-compose.prod.yml logs -f api worker
docker compose -f docker-compose.prod.yml exec postgres pg_isready
curl -H 'X-Admin-API-Key: ...' https://app.example.com/api/admin/queue
```

`/api/health` jest liveness, `/api/health/ready` sprawdza bazę. Publiczne health checki nie ujawniają statystyk kolejki. Ciężkie audio/wideo jest usuwane po udanej transkrypcji; przy błędzie retry pozostaje, a usunięcie źródła czyści cały jego katalog.
