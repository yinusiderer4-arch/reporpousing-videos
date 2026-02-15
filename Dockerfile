FROM python:3.10-slim

# Instala ffmpeg (vital para yt-dlp) y dependencias
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# directorio de trabajo
WORKDIR /app


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY . .


EXPOSE 7860

# Ejecuta la app
CMD ["python", "app.py"]
