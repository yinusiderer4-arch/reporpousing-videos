import os
import yt_dlp
from flask import Flask, render_template, request, jsonify
from groq import Groq

app = Flask(__name__)

# Configuración de Groq
# Recuerda añadir GROQ_API_KEY en las variables de entorno de Render
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def procesar_con_groq(ruta_audio):
    with open(ruta_audio, "rb") as file:
        # Usamos el modelo whisper-large-v3 de Groq (gratuito y ultra rápido)
        transcription = client.audio.transcriptions.create(
            file=(ruta_audio, file.read()),
            model="whisper-large-v3",
            response_format="text",
        )
    return transcription

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/transformar', methods=['POST'])
def transformar():
    url = request.form.get('url')
    nombre_archivo = f"/tmp/audio_{hash(url)}.m4a"
    
    # Recuperamos cookies de los secretos de Render
    cookies_content = os.getenv("YT_COOKIES")
    cookie_path = "/tmp/cookies.txt"
    if cookies_content:
        with open(cookie_path, "w") as f: f.write(cookies_content)

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': nombre_archivo,
        'cookiefile': cookie_path if cookies_content else None,
        'quiet': False,
        'no_warnings': False,
        'nocheckcertificate': True,
        # FORZAMOS SOLO CLIENTE IOS (Es el que menos falla hoy)
        'extractor_args': {
            'youtube': {
                'player_client': ['ios'],
            }
        },
        # User agent de un iPhone moderno
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        texto = procesar_con_groq(nombre_archivo)
        os.remove(nombre_archivo)
        return jsonify({"transcripcion": texto})
    except Exception as e:
        # Esto enviará el error real al frontend en lugar de 'undefined'
        return jsonify({"error": f"Fallo al descargar/procesar: {str(e)}"}), 500

if __name__ == '__main__':
    # SOLUCIÓN AL ERROR DE PUERTOS: Render inyecta el puerto en esta variable
    port = int(os.environ.get("PORT", 7860))
    app.run(host='0.0.0.0', port=port)
