FROM python:3.11-slim

# Instalar dependencias
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libopus0 \
        libsndfile1 \
        ffmpeg \
        iputils-ping \
        && rm -rf /var/lib/apt/lists/*

# Ajustes de red
RUN echo 'net.core.rmem_max = 16777216' >> /etc/sysctl.conf && \
    echo 'net.core.wmem_max = 16777216' >> /etc/sysctl.conf

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "bot.py"]