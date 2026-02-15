FROM python:3.10-slim

# 1. Herramientas y Node.js 20
RUN apt-get update && apt-get install -y \
    ffmpeg curl git \
    && curl -sL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2. Motor de tokens dentro de /app para evitar problemas de permisos
WORKDIR /app
RUN git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /app/bgutil-engine
WORKDIR /app/bgutil-engine/server
RUN npm install
# Compilamos a un archivo JS estándar en una ruta que controlamos
RUN npx esbuild src/generate_once.ts --platform=node --bundle --format=esm --outfile=/app/motor_tokens.js --external:canvas --external:jsdom

# 3. Preparación de la App Python
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Permisos totales para el motor
RUN chmod 755 /app/motor_tokens.js

ENV PORT=7860
ENV PATH="/usr/bin:/usr/local/bin:${PATH}"
EXPOSE 7860

CMD ["python", "app.py"]]

