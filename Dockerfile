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
COPY pyproject.toml README.md ./

RUN pip install --no-cache-dir -e .

ENV DATA_DIR=/app/data
ENV MEDIA_DIR=/app/data/media
ENV DATABASE_URL=sqlite:////app/data/app.db
ENV PYTHONPATH=/app/backend

RUN mkdir -p /app/data/media

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]