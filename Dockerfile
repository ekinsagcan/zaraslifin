# Python 3.10 slim tabanlı imaj
FROM python:3.10-slim

# 1. Gerekli temel araçları kuruyoruz
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    ca-certificates \
    curl \
    gnupg \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 2. Google Chrome'u direkt .deb paketi olarak indirip kuruyoruz
# Bu yöntem apt-key sorununu (Exit code 127) kesin olarak çözer.
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Çalışma dizini ayarla
WORKDIR /app

# Dosyaları kopyala
COPY . .

# Python kütüphanelerini kur
RUN pip install --no-cache-dir -r requirements.txt

# Botu başlat
CMD ["python", "main.py"]
