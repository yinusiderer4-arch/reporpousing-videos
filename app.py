import os
import yt_dlp
import subprocess
from flask import Flask, render_template, request, jsonify
from groq import Groq
import logging
import shutil

app = Flask(__name__)

# Configuración de Groq
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

class MyLogger:
    def debug(self, msg):
        if msg.startswith('[debug] ') or msg.startswith('[youtube]'):
            print(msg)
    def info(self, msg): print(msg)
    def warning(self, msg): print(msg)
    def error(self, msg): print(msg)
def formatear_transcripcion(texto_plano):
    """Usa Llama 3 para añadir párrafos, mayúsculas y corregir errores."""
    try:
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "Eres un editor experto. Tu tarea es coger una transcripción en bruto y darle formato: añade párrafos lógicos, pon mayúsculas donde falten y corrige palabras mal transcritas por el audio. Devuelve solo el texto formateado, sin comentarios extras."},
                {"role": "user", "content": texto_plano}
            ]
        )
        return completion.choices[0].message.content
    except:
        return texto_plano # Si falla la IA de formato, devolvemos el texto original
def comprimir_audio(ruta_original):
    """
    Usa ffmpeg para bajar el peso del archivo drásticamente.
    Convierte a mono, baja el muestreo a 16kHz y el bitrate a 32kbps.
    """
    ruta_comprimido = ruta_original.rsplit('.', 1)[0] + "_lite.mp3"
    try:
        comando = [
            "ffmpeg", "-y", "-i", ruta_original,
            "-vn", "-ar", "16000", "-ac", "1", "-b:a", "32k",
            ruta_comprimido
        ]
        # Ejecutamos el comando de sistema
        subprocess.run(comando, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return ruta_comprimido
    except Exception as e:
        print(f"Error al comprimir: {e}")
        return ruta_original # Si falla, intentamos con el original

def procesar_con_groq(ruta_audio):
    """Envía el audio (ya comprimido) a Groq."""
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/subir', methods=['POST'])
def subir_archivo():
    if 'file' not in request.files:
        return jsonify({"error": "No hay archivo"}), 400
    
    archivo = request.files['file']
    ruta_temp = f"/tmp/{archivo.filename}"
    archivo.save(ruta_temp)
    
    # LLAMADA A LA FUNCIÓN: Comprimimos antes de enviar
    ruta_para_groq = comprimir_audio(ruta_temp)
    
    texto = procesar_con_groq(ruta_para_groq)
    
    # Limpieza: Borramos ambos archivos
    if os.path.exists(ruta_temp): os.remove(ruta_temp)
    if os.path.exists(ruta_para_groq) and ruta_para_groq != ruta_temp:
        os.remove(ruta_para_groq)
    
    return jsonify({"transcripcion": texto})

@app.route('/transformar', methods=['POST'])
def transformar():
    url = request.form.get('url')
    # Ruta absoluta verificada por tu diagnóstico
    path_js = '/app/motor_tokens.js'
    
    print(f"--- INICIANDO DESCARGA ---")
    print(f"Ruta motor: {path_js} | Existe: {os.path.exists(path_js)}")

    ydl_opts = {
        'verbose': True,
        'format': 'bestaudio/best',
        'outtmpl': f'/tmp/audio_{hash(url)}.m4a',
        'nocheckcertificate': True,
        # IMPORTANTE: Estructura exacta para el plugin bgutil:script
        'extractor_args': {
            'youtubepot-bgutilscript': {
                'script_path': path_js
            },
            'youtube': {
                'player_client': ['android'], # Solo Android, es el más estable con POT
                'player_skip': ['web', 'tv']   # Saltamos TV para evitar tu sospecha
            }
        },
        'js_runtimes': {'node': {}}
    }

    try:
        # 4. DESCARGA
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # 5. PROCESAMIENTO (¡Esto no lo toques!)
        # Comprimir -> Transcribir -> Formatear
        ruta_para_groq = comprimir_audio(nombre_original)
        texto_bruto = procesar_con_groq(ruta_para_groq)
        texto_final = formatear_transcripcion(texto_bruto)

        # 6. LIMPIEZA
        if os.path.exists(nombre_original): os.remove(nombre_original)
        if os.path.exists(ruta_para_groq): os.remove(ruta_para_groq)
            
        return jsonify({"transcripcion": texto_final})

    except Exception as e:
        return jsonify({"error": f"Error técnico: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 7860))
    app.run(host='0.0.0.0', port=port)
