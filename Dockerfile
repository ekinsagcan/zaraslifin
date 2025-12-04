# Python 3.10 kullanıyoruz
FROM python:3.10-slim

# Sistem güncellemeleri ve Chrome kurulumu
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    ca-certificates \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Çalışma dizini
WORKDIR /app

# Dosyaları kopyala
COPY . .

# Python kütüphanelerini kur
RUN pip install --no-cache-dir -r requirements.txt

# Botu başlat
CMD ["python", "main.py"]
