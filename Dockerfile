# Usamos una imagen de Python moderna
FROM python:3.10-slim

# Instalamos ffmpeg y herramientas de sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Creamos un usuario para Hugging Face (seguridad)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:${PATH}"

WORKDIR /app

# Copiamos los requisitos e instalamos
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código
COPY --chown=user . .

# Puerto que usa Hugging Face
EXPOSE 7860

CMD ["python", "app.py"]