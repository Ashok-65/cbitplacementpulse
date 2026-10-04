FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=5000

WORKDIR /app

COPY Backend/requirements.txt ./Backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r ./Backend/requirements.txt

COPY Backend ./Backend
COPY Frontend ./Frontend

RUN mkdir -p /app/Backend/instance

EXPOSE 5000

WORKDIR /app/Backend

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-5000} app:app"]
