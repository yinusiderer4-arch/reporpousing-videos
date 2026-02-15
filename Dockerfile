FROM python:3.10-slim

# 1. Instalamos Node 20 (La versión que yt-dlp prefiere)
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

# --- LA CORRECCIÓN MAESTRA ---
# Compilamos a 'generate_once.js' (aunque sea ESM) para que el plugin lo acepte
RUN npx esbuild src/generate_once.ts --platform=node --format=esm --outfile=generate_once.js

# 3. Preparamos la App
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Permisos
RUN chmod 755 /app/bgutil-engine/server/generate_once.js

ENV PORT=7860
EXPOSE 7860

CMD ["python", "app.py"]

