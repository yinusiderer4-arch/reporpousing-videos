FROM python:3.10-slim

# Instalación limpia de dependencias
RUN apt-get update && apt-get install -y \
    ffmpeg curl git \
    && curl -sL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Verificar que node funciona y está en /usr/bin/node
RUN node -v 

# Preparar motor de tokens
WORKDIR /app
RUN git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /app/bgutil-engine
WORKDIR /app/bgutil-engine/server
RUN npm install

# Configurar App
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Aseguramos que el plugin esté en su sitio
RUN ls -R yt_dlp_plugins/

ENV PORT=7860
# Forzamos a Node al PATH por si acaso
ENV PATH="/usr/bin:/usr/local/bin:${PATH}"

CMD ["python", "app.py"]

