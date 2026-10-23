FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn
COPY . .
EXPOSE 8000
# Mismo arranque que produccion (App Service): migrar, recolectar estaticos y
# servir con 2 workers. Requiere DJANGO_SECRET_KEY y DATABASE_URL.
CMD ["sh", "-c", "python gotogym/manage.py migrate --noinput && python gotogym/manage.py collectstatic --noinput && exec gunicorn --chdir gotogym gotogym.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120 --error-logfile -"]
