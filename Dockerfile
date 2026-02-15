FROM python:3.10-slim

# 1. Instalamos todo lo necesario y configuramos Node.js 18
RUN apt-get update && apt-get install -y \
    ffmpeg curl git \
    && curl -sL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2. Instalamos el motor de tokens en el HOME (donde el plugin lo busca por defecto)
WORKDIR /root
RUN git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git bgutil-ytdlp-pot-provider
WORKDIR /root/bgutil-ytdlp-pot-provider/server
RUN npm install
# Creamos la carpeta 'build' y el enlace que el plugin espera encontrar
RUN mkdir -p build && ln -s ../generate_once.js build/generate_once.js

# 3. Preparamos nuestra App
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# 4. Forzamos a que Node y el motor estén en el PATH
ENV PATH="/usr/bin:/usr/local/bin:${PATH}"
ENV PORT=7860
EXPOSE 7860

CMD ["python", "app.py"]

