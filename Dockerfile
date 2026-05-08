FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-kor \
    fonts-nanum \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

# 한 번에 여러 장 OCR 시 30초 기본 타임아웃으로 끊기므로 충분히 길게 설정
CMD ["sh", "-c", "exec gunicorn --workers 1 --threads 1 --timeout 600 --graceful-timeout 60 --bind 0.0.0.0:${PORT:-10000} app:app"]
