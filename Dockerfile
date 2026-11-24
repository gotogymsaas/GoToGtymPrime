FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# Mismo arranque que el versionado para App Service: migrar, recolectar
# estaticos, cargar el Journal y servir con gunicorn de hilos. Los valores de
# gunicorn viven solo en environments/azure/startup.sh. Requiere
# DJANGO_SECRET_KEY y DATABASE_URL.
CMD ["bash", "environments/azure/startup.sh"]
