FROM python:3.10-slim

# 1. Herramientas y Node.js 18
RUN apt-get update && apt-get install -y \
    ffmpeg curl git \
    && curl -sL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2. Instalación del motor de tokens
WORKDIR /app
RUN git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /app/bgutil-engine

WORKDIR /app/bgutil-engine/server
RUN npm install

# --- LA SOLUCIÓN TÉCNICA ---
# Compilamos el TypeScript a JavaScript pero SIN empaquetar las librerías externas.
# Usamos el formato 'esm' y la extensión '.js' para que Node acepte "import.meta".
RUN npx esbuild src/generate_once.ts --platform=node --format=esm --outfile=generate_once.js

# 3. Preparación de la App Python
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Permisos
RUN chmod 755 /app/bgutil-engine/server/generate_once.mjs

ENV PORT=7860
ENV PATH="/usr/bin:/usr/local/bin:${PATH}"
EXPOSE 7860

CMD ["python", "app.py"]

