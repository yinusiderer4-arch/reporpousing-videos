FROM python:3.10-slim

# 1. Node 20 (Estándar actual)
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

# --- EL TRUCO CJS ---
# --format=cjs: Obliga a usar 'require' (más compatible y robusto)
# --outfile=...js: Mantiene la extensión .js que el plugin exige
# --platform=node: Asegura que funcionen los módulos nativos
RUN npx esbuild src/generate_once.ts --bundle --platform=node --format=cjs --outfile=/app/generate_once.js --external:canvas --external:jsdom

# 3. App Python
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
