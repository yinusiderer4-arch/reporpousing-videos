FROM python:3.10-slim

# 1. Instalamos dependencias y Node.js
RUN apt-get update && apt-get install -y \
    ffmpeg curl git \
    && curl -sL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2. Instalamos el motor de tokens dentro de /app
WORKDIR /app
RUN git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /app/bgutil-engine
WORKDIR /app/bgutil-engine/server
RUN npm install
# Creamos la carpeta build y movemos el script ahí para que el plugin lo encuentre solo
RUN mkdir -p build && cp generate_once.js build/generate_once.js

# 3. Preparamos tu App
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# 4. Aseguramos permisos de ejecución
RUN chmod -R 755 /app/bgutil-engine

ENV PORT=7860
EXPOSE 7860

CMD ["python", "app.py"]

