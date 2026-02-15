FROM python:3.10-slim

# 1. Instalamos Node 20 y dependencias de compilación para Canvas
RUN apt-get update && apt-get install -y \
    ffmpeg curl git build-essential libcairo2-dev libpango1.0-dev libjpeg-dev \
    libgif-dev librsvg2-dev \
    && curl -sL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2. Preparamos el entorno en /app
WORKDIR /app

# --- PASO CRÍTICO: Instalar dependencias donde va a vivir el script ---
# Instalamos jsdom y canvas aquí mismo para que el script los encuentre
RUN npm install jsdom canvas

# 3. Clonamos y construimos el motor
RUN git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /app/bgutil-engine
WORKDIR /app/bgutil-engine/server
RUN npm install
# Compilamos a CJS y lo enviamos a /app/generate_once.js
# Mantenemos 'external' porque ahora SÍ estarán en /app/node_modules
RUN npx esbuild src/generate_once.ts --bundle --platform=node --format=cjs --outfile=/app/generate_once.js --external:canvas --external:jsdom

# 4. Volvemos a /app y copiamos tu código Python
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Permisos
RUN chmod 755 /app/generate_once.js

ENV PORT=7860
ENV PATH="/usr/bin:/usr/local/bin:${PATH}"
EXPOSE 7860

CMD ["python", "app.py"]
