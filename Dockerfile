FROM python:3.10-slim

# 1. Instalamos herramientas y Node.js
RUN apt-get update && apt-get install -y \
    ffmpeg curl git \
    && curl -sL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2. Preparamos el motor de tokens
WORKDIR /app
RUN git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /app/bgutil-engine

# Entramos donde están las dependencias de Node y las instalamos
WORKDIR /app/bgutil-engine/server
RUN npm install

# --- EL TRUCO MAESTRO ---
# Buscamos el archivo generate_once.js en cualquier subcarpeta y lo movemos a /app/motor.js
RUN find /app/bgutil-engine -name "generate_once.js" -exec cp {} /app/motor.js \;

# 3. Preparamos la App de Python
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Permisos de ejecución para el motor
RUN chmod 755 /app/motor.js

ENV PORT=7860
ENV PATH="/usr/bin:/usr/local/bin:${PATH}"
EXPOSE 7860

CMD ["python", "app.py"]

