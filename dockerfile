FROM python:3.11-slim

# Instalar dependencias del sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libopus0 \
        libsndfile1 \
        ffmpeg \
        && rm -rf /var/lib/apt/lists/*

# Copiar código
WORKDIR /app
COPY . /app

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Ejecutar el bot
CMD ["python", "bot.py"]