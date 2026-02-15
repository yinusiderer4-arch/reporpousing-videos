FROM python:3.10-slim

# 1. Herramientas básicas
RUN apt-get update && apt-get install -y \
    ffmpeg curl git \
    && curl -sL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2. Clonamos el motor de tokens
WORKDIR /app
RUN git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /app/bgutil-engine

# --- PASO DE INVESTIGACIÓN ---
# Este comando imprimirá TODO lo que hay dentro de la carpeta clonada en tus logs de Render
RUN echo "--- LISTADO DE ARCHIVOS ENCONTRADOS ---" && ls -R /app/bgutil-engine

WORKDIR /app/bgutil-engine/server
RUN npm install

# 3. Intentamos una copia manual (asumiendo la ruta más probable)
# Si este comando falla, no detendrá el build (gracias al '|| true')
RUN cp /app/bgutil-engine/server/generate_once.js /app/motor.js || true

# 4. App de Python
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PORT=7860
EXPOSE 7860

CMD ["python", "app.py"]
CMD ["python", "app.py"]

