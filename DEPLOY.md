# Wdrożenie produkcyjne

Produkcyjny stack składa się z PostgreSQL, API, osobnego workera i Caddy. Na współdzielonym OVH Caddy słucha wyłącznie na `127.0.0.1:8082`, istniejący nginx przyjmuje ruch na porcie 80, a darmowy adres Vercela zapewnia publiczne HTTPS. InvestTracker i Policzalne zachowują własne nazwane vhosty nginx. API wykonuje migracje Alembic przed startem, a worker czeka na gotowość API i bazy.

> Nie używaj na tym współdzielonym serwerze ogólnego `scripts/vps_setup.sh`. Poniższa procedura zachowuje istniejące usługi i porty.

## Pierwsze uruchomienie

1. Połącz się z OVH poleceniem `ssh -i ~/.ssh/investtracker-ovh ubuntu@57.131.51.89` i ponownie sprawdź, że port `8082` oraz podsieć `172.28.0.0/24` są wolne.
2. Sklonuj `main` do osobnego katalogu, skopiuj `.env.example` do `.env`, ustaw prawa `600` i wpisz sekrety bezpośrednio na VPS.
3. Zaimportuj repozytorium do Vercela. `vercel.json` przekazuje ruch do publicznego IP OVH `57.131.51.89`; ustaw `PUBLIC_BASE_URL` oraz `ALLOWED_ORIGINS` na otrzymany adres `https://projekt.vercel.app`.
4. Ustaw `SINGLE_USER_EMAIL` na adres właściciela konta Resend, `RESEND_FROM_EMAIL=onboarding@resend.dev` i skonfiguruj Turnstile wyłącznie dla hosta Vercela.
5. Ustaw `LLM_PROVIDER=openrouter`, osobny `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1` oraz `OPENROUTER_MODEL=google/gemini-3.1-flash-lite`.
6. Uruchom stack:

```bash
DOMAIN=:80 docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
curl -fsS http://127.0.0.1:8082/api/health/ready
```

7. Dodaj fallback vhost nginx dopiero po sprawdzeniu jego konfiguracji:

```bash
sudo cp deploy/nginx-video-analizier.conf /etc/nginx/sites-available/video-analizier
sudo ln -s /etc/nginx/sites-available/video-analizier /etc/nginx/sites-enabled/video-analizier
sudo nginx -t
sudo systemctl reload nginx
curl -fsS http://57.131.51.89/api/health/ready
curl -fsS https://projekt.vercel.app/api/health/ready
```

Przed i po przeładowaniu nginx sprawdź `https://api.investtracker.eu/health` oraz `https://api.policzalne.pl/api/health`. W produkcji wymagane są `PUBLIC_BASE_URL`, `SINGLE_USER_EMAIL`, `ADMIN_API_KEY`, `POSTGRES_PASSWORD`, dane Resend, oba klucze Turnstile oraz co najmniej jeden serwerowy klucz LLM. `AUTH_REQUIRED=true` i `COOKIE_SECURE=true` są wymuszane przez Compose. Kluczy LLM nie podaje się w UI ani w konfiguracji Vercela. Vercel i Caddy jawnie wyłączają cache odpowiedzi aplikacji.

## Aktualizacja

```bash
./scripts/backup_postgres.sh
git pull --ff-only origin main
DOMAIN=:80 docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
curl -fsS http://127.0.0.1:8082/api/health/ready
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
