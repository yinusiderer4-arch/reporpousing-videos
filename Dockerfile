FROM python:3.10-slim

# 1. Instalamos Node 20 (Necesario para el reto matemático de YouTube)
RUN apt-get update && apt-get install -y \
    ffmpeg curl git \
    && curl -sL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2. Instalamos el motor de tokens en la RUTA NATIVA del plugin
# El plugin busca en ~/bgutil-ytdlp-pot-provider/server/build/generate_once.js
WORKDIR /root
RUN git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git
WORKDIR /root/bgutil-ytdlp-pot-provider/server
RUN npm install
# Compilamos forzando la exclusión de librerías conflictivas y con el nombre exacto .js
RUN npx esbuild src/generate_once.ts --platform=node --bundle --format=esm --outfile=build/generate_once.js --external:canvas --external:jsdom

# 3. Configuramos tu App de Python
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PORT=7860
ENV PATH="/usr/bin:/usr/local/bin:${PATH}"
EXPOSE 7860

CMD ["python", "app.py"]

