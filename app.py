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
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key: return {"error": "Falta API Key"}

    client = Groq(api_key=api_key)
    
    # 1. PROMPT EXACTO
    prompt = """
    Actúa como un estratega de contenido viral.
    Tu objetivo es transformar la siguiente transcripción en piezas de contenido listas para publicar.
    
    IMPORTANTE: Responde ÚNICAMENTE con un JSON válido. Sin texto introductorio.
    Usa EXACTAMENTE estas claves:
    
    {
        "resumen": "Resumen potente en 3 frases",
        "hilo_twitter": ["Tweet 1", "Tweet 2", "Tweet 3", "Tweet 4", "Tweet 5"],
        "linkedin": "Texto para LinkedIn profesional con emojis",
        "tiktok_script": "Guion con indicaciones [VISUAL] y [AUDIO]"
    }
    """

    try:
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Transcripción:\n{texto_transcrito[:25000]}"}
            ],
            model="llama3-70b-8192", 
            temperature=0.5, # Bajamos temperatura para que sea más obediente con el JSON
            response_format={"type": "json_object"}
        )
        
        contenido_bruto = completion.choices[0].message.content
        print(f"--- RESPUESTA RAW GROQ (DEBUG) ---\n{contenido_bruto[:200]}...\n--------------------------------")
        
        return json.loads(contenido_bruto)
        
    except Exception as e:
        print(f"❌ ERROR JSON PACK VIRAL: {e}")
        # Devolvemos un objeto vacío con el error para que el frontend no muestre "undefined"
        return {
            "resumen": "Error generando resumen: " + str(e),
            "hilo_twitter": ["Error"],
            "linkedin": "Error",
            "tiktok_script": "Error"
        }

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
# --- RUTA TRANSFORMAR ---
@app.route('/transformar', methods=['POST'])
def transformar():
    url = request.form.get('url')
    
    # Rutas
    nombre_original = f'/tmp/audio_{hash(url)}.m4a'
    
    # Cookies
    cookies_content = os.getenv("YT_COOKIES")
    cookie_path = "/tmp/cookies.txt"
    if cookies_content:
        with open(cookie_path, "w") as f:
            f.write(cookies_content)
    
    # Configuración yt-dlp
    ydl_opts = {
        'verbose': True,
        'format': 'bestaudio/best',
        'outtmpl': nombre_original,
        'nocheckcertificate': True,
        'cookiefile': cookie_path if cookies_content else None,
        'remote_components': ['ejs:github'], 
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

        # --- AQUI ESTABA EL FALLO ANTES ---
        # Hay que comprimir SIEMPRE antes de enviar a Groq
        print("--- 2. COMPRIMIENDO (Vital para Groq) ---")
        ruta_comprimida = comprimir_audio(nombre_original)

        print("--- 3. TRANSCRIBIENDO ---")
        # Usamos la ruta comprimida, no la original
        texto_crudo = procesar_con_groq(ruta_comprimida)
        
        # Verificamos que no sea un error de transcripción
        if isinstance(texto_crudo, str) and texto_crudo.startswith("Error"):
             return jsonify({"transcripcion": texto_crudo, "pack_viral": None})

        print("--- 4. GENERANDO PACK VIRAL ---")
        pack_social = generar_pack_viral(texto_crudo)
        
        # Limpieza
        if os.path.exists(nombre_original): os.remove(nombre_original)
        if os.path.exists(ruta_comprimida) and ruta_comprimida != nombre_original:
            os.remove(ruta_comprimida)
            
        return jsonify({
            "status": "success",
            "transcripcion": texto_crudo,
            "pack_viral": pack_social 
        })

    except Exception as e:
        print(f"❌ ERROR CRÍTICO: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 7860))
    app.run(host='0.0.0.0', port=port)
