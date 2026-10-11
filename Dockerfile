FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 DATABASE_PATH=/data/market.db UPLOAD_FOLDER=/data/uploads
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /data
EXPOSE 8000
CMD ["sh", "-c", "gunicorn wsgi:app --workers 2 --threads 4 --bind 0.0.0.0:${PORT:-8000}"]
