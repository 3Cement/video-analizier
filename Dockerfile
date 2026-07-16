FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY pyproject.toml README.md ./

RUN pip install --no-cache-dir -e .

ENV DATA_DIR=/app/data
ENV MEDIA_DIR=/app/data/media
ENV PYTHONPATH=/app/backend

RUN mkdir -p /app/data/media

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
