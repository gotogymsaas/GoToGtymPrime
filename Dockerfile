# FROM python:3.11-slim
# ENV PYTHONDONTWRITEBYTECODE=1
# ENV PYTHONUNBUFFERED=1
# WORKDIR /app
# COPY requirements.txt /app/
# RUN pip install --no-cache-dir -r requirements.txt
# COPY . /app
# CMD ["python", "gotogym/manage.py", "runserver", "0.0.0.0:8000"]

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
# (Opcional) deps de sistema si usas psycopg2, pillow, etc.
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq5 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn
COPY ..
EXPOSE 8000
CMD ["sh","-c","gunicorn gotogym.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WORKERS:-3} --timeout 120"]
