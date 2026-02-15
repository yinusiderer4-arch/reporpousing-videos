FROM python:3.10-slim

# Instalamos ffmpeg Y nodejs (el motor para resolver el reto de YouTube)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && curl -sL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render usa el puerto dinámico, Flask lo gestionará
CMD ["python", "app.py"]
