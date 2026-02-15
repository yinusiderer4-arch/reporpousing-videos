FROM python:3.10-slim

# 1. Instalamos Node 20 y dependencias de compilación
RUN apt-get update && apt-get install -y \
    ffmpeg curl git \
    && curl -sL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2. Preparamos el motor
WORKDIR /app
RUN git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /app/bgutil-engine
WORKDIR /app/bgutil-engine/server
RUN npm install

# --- LA CORRECCIÓN CLAVE ---
# El archivo DEBE llamarse generate_once.js para que el plugin de Python lo acepte.
# Incluimos 'jsdom' para que el reto de YouTube sea indistinguible de un humano.
RUN npx esbuild src/generate_once.ts --platform=node --bundle --format=esm --outfile=/app/generate_once.js --external:canvas

# 3. App Python
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN chmod 755 /app/generate_once.js

ENV PORT=7860
ENV PATH="/usr/bin:/usr/local/bin:${PATH}"
EXPOSE 7860

CMD ["python", "app.py"]
