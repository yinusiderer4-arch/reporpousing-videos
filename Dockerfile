FROM python:3.10-slim

# 1. Instalamos herramientas del sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    git \
    && curl -sL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2. Preparamos el generador de PO Tokens
WORKDIR /app
RUN git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /app/bgutil-engine

# Entramos en la carpeta del servidor e instalamos solo las dependencias
WORKDIR /app/bgutil-engine/server
RUN npm install

# 3. Configuramos la aplicación de Python
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto de tu código (incluyendo la carpeta yt_dlp_plugins)
COPY . .

# Configuración de puerto para Render
ENV PORT=7860
EXPOSE 7860

CMD ["python", "app.py"]
