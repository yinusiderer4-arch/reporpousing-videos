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
    if not url:
        return jsonify({"error": "URL no válida"}), 400

    nombre_archivo = f"/tmp/audio_{hash(url)}.m4a"
    
    # Descarga ligera (solo audio)
    ydl_opts = {
        'format': '140',
        'outtmpl': nombre_archivo,
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Mandar a Groq
        texto = procesar_con_groq(nombre_archivo)
        
        # Limpiar
        if os.path.exists(nombre_archivo):
            os.remove(nombre_archivo)
            
        return jsonify({"transcripcion": texto})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # SOLUCIÓN AL ERROR DE PUERTOS: Render inyecta el puerto en esta variable
    port = int(os.environ.get("PORT", 7860))
    app.run(host='0.0.0.0', port=port)
