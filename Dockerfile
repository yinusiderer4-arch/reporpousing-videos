FROM python:3.10-slim

# 1. Instalamos Node 20 (Necesario para el reto de YouTube)
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

# --- LA CIRUGÍA ---
# 1. Formato CJS (para que Node no se queje del require)
# 2. Extensión .js (para que el plugin no se queje del nombre)
# 3. Ruta /app/generate_once.js (la que hemos hardcodeado en el python)
RUN npx esbuild src/generate_once.ts --bundle --platform=node --format=cjs --outfile=/app/generate_once.js --external:canvas --external:jsdom

# 3. Copiamos tu App y el Plugin MODIFICADO
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
