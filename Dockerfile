FROM python:3.10-slim

# Instalamos ffmpeg y Node.js de forma robusta
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && curl -sL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Importante para que Render vea el puerto
ENV PORT=7860
EXPOSE 7860

CMD ["python", "app.py"]
