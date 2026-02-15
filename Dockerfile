FROM python:3.10-slim

# 1. Herramientas y Node.js
RUN apt-get update && apt-get install -y \
    ffmpeg curl git \
    && curl -sL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2. Preparamos el motor de tokens
WORKDIR /app
RUN git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /app/bgutil-engine

# Entramos en la carpeta del servidor e instalamos dependencias
WORKDIR /app/bgutil-engine/server
RUN npm install

# --- LA CLAVE: COMPILAR TYPESCRIPT A JAVASCRIPT ---
# Usamos npx para ejecutar esbuild sin instalarlo globalmente
# Esto crea /app/motor.js unificando todo el código
RUN npx esbuild src/generate_once.ts --bundle --platform=node --outfile=/app/motor.js

# 3. Preparamos la App de Python
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Permisos para el nuevo archivo creado
RUN chmod 755 /app/motor.js

ENV PORT=7860
ENV PATH="/usr/bin:/usr/local/bin:${PATH}"
EXPOSE 7860

CMD ["python", "app.py"]

