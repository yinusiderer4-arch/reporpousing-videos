FROM python:3.10-slim

# 1. Instalamos dependencias del sistema (todo en un solo paso para ahorrar espacio)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    git \
    && curl -sL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2. Preparamos el motor de PO Tokens (La "Magia Negra")
# Clonamos el repositorio
RUN git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /app/bgutil-engine

# ¡AQUÍ ESTABA EL ERROR! Entramos en la carpeta 'server' donde está el package.json
WORKDIR /app/bgutil-engine/server

# Instalamos las dependencias de Node.js y compilamos el generador
RUN npm install && npm run build

# 3. Configuramos nuestra aplicación de Python
WORKDIR /app

# Copiamos e instalamos librerías de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto de tu código (incluida la carpeta yt_dlp_plugins)
COPY . .

# Configuración de puerto para Render
ENV PORT=7860
EXPOSE 7860

# Arrancamos la web
CMD ["python", "app.py"]
