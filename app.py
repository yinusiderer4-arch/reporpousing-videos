import os
import json
import yt_dlp
import subprocess
from flask import Flask, render_template, request, jsonify
from groq import Groq
import logging
import shutil

app = Flask(__name__)

# Configuración Global de Groq
# Usamos esta instancia global para no crear una nueva en cada petición
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# --- FUNCIONES AUXILIARES ---

def comprimir_audio(ruta_original):
    """
    Usa ffmpeg para bajar el peso del archivo drásticamente.
    Convierte a mono, baja el muestreo a 16kHz y el bitrate a 32kbps.
    Esto es VITAL para no superar el límite de 25MB de Groq.
    """
    # Creamos un nombre para el archivo ligero
    ruta_comprimido = ruta_original.rsplit('.', 1)[0] + "_lite.mp3"
    
    print(f"--- COMPRIMIENDO AUDIO: {ruta_original} -> {ruta_comprimido} ---")
    
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
        # Si falla la compresión, devolvemos el original y rezamos para que pese menos de 25MB
        return ruta_original 

def procesar_con_groq(ruta_audio):
    """Envía el audio a Whisper de Groq para transcribir."""
    try:
        with open(ruta_audio, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(ruta_audio), file.read()), # Enviamos nombre y bytes
                model="whisper-large-v3",
                response_format="text", # Pedimos texto plano
            )
        return transcription
    except Exception as e:
        return f"Error en Groq: {str(e)}"

def generar_pack_viral(texto_transcrito):
    """Genera el contenido para redes sociales usando Llama 3."""
    # Usamos el cliente global definido arriba
    
    prompt = """
    Actúa como un estratega de contenido viral.
    Tu objetivo es transformar la siguiente transcripción en piezas de contenido listas para publicar.
    
    Devuelve la respuesta ESTRICTAMENTE en formato JSON con estas claves:
    1. "resumen": Un resumen del video en 3 frases potentes.
    2. "hilo_twitter": Una lista (array) de 5 tweets (gancho + desarrollo + conclusión).
    3. "linkedin": Un post profesional con emojis y estructura de valor.
    4. "tiktok_script": Un guion paso a paso con indicaciones visuales [VISUAL] y de audio [AUDIO].
    """

    try:
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt},
                # Recortamos a 25k caracteres para no saturar el contexto
                {"role": "user", "content": f"Transcripción:\n{texto_transcrito[:25000]}"}
            ],
            model="llama3-70b-8192", 
            temperature=0.6,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"Error generando pack viral: {e}")
        # Devolvemos un JSON vacío pero seguro para no romper el frontend
        return {"error": "No se pudo generar el contenido viral", "detalle": str(e)}

# --- RUTAS DE LA APLICACIÓN ---

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
    
    # 1. Comprimir
    ruta_para_groq = comprimir_audio(ruta_temp)
    
    # 2. Transcribir
    texto = procesar_con_groq(ruta_para_groq)
    
    # 3. Limpieza
    if os.path.exists(ruta_temp): os.remove(ruta_temp)
    if os.path.exists(ruta_para_groq) and ruta_para_groq != ruta_temp:
        os.remove(ruta_para_groq)
    
    return jsonify({"transcripcion": texto})

@app.route('/transformar', methods=['POST'])
def transformar():
    url = request.form.get('url')
    
    # Definimos nombre único y ruta
    nombre_original = f'/tmp/audio_{hash(url)}.m4a'
    
    # Gestión de Cookies
    cookies_content = os.getenv("YT_COOKIES")
    cookie_path = "/tmp/cookies.txt"
    if cookies_content:
        with open(cookie_path, "w") as f:
            f.write(cookies_content)
    
    # Limpieza de caché de yt-dlp
    cache_dir = '/tmp/yt-dlp-cache'
    
    # CONFIGURACIÓN BLINDADA (Descarga robusta)
    ydl_opts = {
        'verbose': True,
        'format': 'bestaudio/best',
        'outtmpl': nombre_original,
        'nocheckcertificate': True,
        'cookiefile': cookie_path if cookies_content else None,
        'cachedir': cache_dir,
        
        # LLAVE MAESTRA (GitHub + Node)
        'remote_components': ['ejs:github'], 
        
        # ANTI-CORTES
        'socket_timeout': 30,
        'retries': 20,
        'fragment_retries': 20,
        'skip_unavailable_fragments': False,
        'buffersize': 1024,
        
        'extractor_args': {
            'youtube': {
                'player_client': ['tv'], 
                'player_skip': ['web', 'web_music', 'android', 'ios']
            }
        },
        'js_runtimes': {'node': {}}
    }

    try:
        print(f"--- 1. DESCARGANDO: {url} ---")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        if not os.path.exists(nombre_original):
             return jsonify({"error": "Fallo en descarga"}), 500

        print("--- 2. COMPRIMIENDO AUDIO (Vital para Groq) ---")
        # ESTO ES LO QUE FALTABA: Comprimir antes de enviar
        ruta_comprimida = comprimir_audio(nombre_original)

        print("--- 3. TRANSCRIBIENDO CON WHISPER ---")
        texto_crudo = procesar_con_groq(ruta_comprimida)
        
        print("--- 4. GENERANDO PACK VIRAL (MARKETING) ---")
        pack_social = generar_pack_viral(texto_crudo)
        
        # LIMPIEZA TOTAL
        # Borramos el original pesado
        if os.path.exists(nombre_original): os.remove(nombre_original)
        # Borramos el comprimido ligero
        if os.path.exists(ruta_comprimida) and ruta_comprimida != nombre_original:
            os.remove(ruta_comprimida)
            
        return jsonify({
            "status": "success",
            "transcripcion": texto_crudo,
            "pack_viral": pack_social
        })

    except Exception as e:
        print(f"❌ ERROR FATAL: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 7860))
    app.run(host='0.0.0.0', port=port)
