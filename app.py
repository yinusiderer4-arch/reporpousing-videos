import os
import yt_dlp
from flask import Flask, render_template, request, jsonify
from groq import Groq
import subprocess

app = Flask(__name__)

# 1. Configuración de Clientes (Groq)
# Asegúrate de tener GROQ_API_KEY en los Secrets de Render
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# 2. Funciones auxiliares
def comprimir_audio(ruta_original):
    ruta_comprimido = ruta_original.replace(".m4a", "_comp.mp3")
    # Bajamos el bitrate a 32k para que un audio de 1 hora ocupe unos 14MB
    comando = [
        "ffmpeg", "-i", ruta_original,
        "-vn", "-ar", "16000", "-ac", "1", "-b:a", "32k",
        ruta_comprimido
    ]
    subprocess.run(comando, check=True)
    return ruta_comprimido
    
def procesar_con_groq(ruta_audio):
    """Envía el audio a la API de Groq para transcripción rápida."""
    try:
        with open(ruta_audio, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(ruta_audio, file.read()),
                model="whisper-large-v3",
                response_format="text",
            )
        return transcription
    except Exception as e:
        return f"Error en Groq: {str(e)}"

# 3. Rutas de la aplicación
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/subir', methods=['POST'])
def subir_archivo():
    """Ruta de respaldo: permite procesar archivos locales si YouTube falla."""
    if 'file' not in request.files:
        return jsonify({"error": "No hay archivo en la petición"}), 400
    
    archivo = request.files['file']
    if archivo.filename == '':
        return jsonify({"error": "No se seleccionó ningún archivo"}), 400

    ruta_temp = f"/tmp/{archivo.filename}"
    archivo.save(ruta_temp)
    
    texto = procesar_con_groq(ruta_temp)
    
    if os.path.exists(ruta_temp):
        os.remove(ruta_temp)
    
    return jsonify({"transcripcion": texto})

@app.route('/transformar', methods=['POST'])
def transformar():
    """Ruta principal: descarga de YouTube y transcripción."""
    url = request.form.get('url')
    if not url:
        return jsonify({"error": "URL no proporcionada"}), 400

    nombre_archivo = f"/tmp/audio_{hash(url)}.m4a"
    
    # Manejo de Cookies desde variables de entorno
    cookies_content = os.getenv("YT_COOKIES")
    cookie_path = "/tmp/cookies.txt"
    if cookies_content:
        with open(cookie_path, "w") as f:
            f.write(cookies_content)

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': nombre_archivo,
        'cookiefile': cookie_path if cookies_content else None,
        'quiet': False,
        'no_warnings': False,
        'nocheckcertificate': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['web_safari'],
                'skip': ['hls', 'dash'],
            }
        },
        'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Si yt-dlp descargó un archivo con otra extensión (ej. .webm), lo buscamos
        archivo_real = None
        for f in os.listdir("/tmp"):
            if f.startswith(f"audio_{hash(url)}"):
                archivo_real = os.path.join("/tmp", f)
                break
        
        if not archivo_real:
            return jsonify({"error": "No se encontró el archivo descargado"}), 500

        texto = procesar_con_groq(archivo_real)
        os.remove(archivo_real)
        
        return jsonify({"transcripcion": texto})
    
    except Exception as e:
        return jsonify({"error": f"Fallo al descargar/procesar: {str(e)}"}), 500

# 4. Arranque del servidor
if __name__ == '__main__':
    # Puerto dinámico para Render
    port = int(os.environ.get("PORT", 7860))
    app.run(host='0.0.0.0', port=port)
