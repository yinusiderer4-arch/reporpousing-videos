import os
import json
import yt_dlp
import subprocess
from flask import Flask, render_template, request, jsonify
from groq import Groq
import uuid  # <--- IMPORTANTE: Para generar nombres únicos
import shutil

app = Flask(__name__)

# Límite de tamaño de archivo (ej: 500MB) para evitar ataques de denegación de servicio
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024 

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

ALLOWED_EXTENSIONS = {'mp3', 'wav', 'm4a', 'mp4', 'mpeg', 'ogg', 'webm'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- FUNCIONES AUXILIARES ---

def comprimir_audio(ruta_original):
    # Generamos un nombre único también para el comprimido
    nombre_seguro = f"{os.path.dirname(ruta_original)}/{uuid.uuid4()}_lite.mp3"
    
    print(f"--- COMPRIMIENDO: {ruta_original} -> {nombre_seguro} ---")
    
    try:
        comando = [
            "ffmpeg", "-y", "-i", ruta_original,
            "-vn", "-ar", "16000", "-ac", "1", "-b:a", "32k",
            nombre_seguro
        ]
        subprocess.run(comando, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return nombre_seguro
    except Exception as e:
        print(f"Error compresión: {e}")
        return ruta_original 

def procesar_con_groq(ruta_audio):
    try:
        with open(ruta_audio, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(ruta_audio), file.read()), 
                model="whisper-large-v3",
                response_format="text", 
            )
        return transcription
    except Exception as e:
        return f"Error en Groq: {str(e)}"

def generar_pack_viral(texto_transcrito):
    # ... (Tu función generadora igual que antes) ...
    # Solo asegúrate de que el modelo sea el nuevo:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key: return {"error": "Falta API Key"}
    client = Groq(api_key=api_key)

    prompt = """
    Actúa como un estratega de contenido viral.
    Tu objetivo es transformar la siguiente transcripción en piezas de contenido listas para publicar.
    
    IMPORTANTE: Responde ÚNICAMENTE con un JSON válido.
    Usa EXACTAMENTE estas claves:
    {
        "resumen": "Resumen potente sobre las ideas clave en 3 frases si el video es corto, o 5 frases si es más largo",
        "hilo_twitter": ["Tweet 1", "Tweet 2", "Tweet 3", "Tweet 4", "Tweet 5"],
        "linkedin": "Texto para LinkedIn profesional con emojis",
        "tiktok_script": "Guion con indicaciones [VISUAL] y [AUDIO] para grabar un reel o copiar y pegar como un prompt para IAs de creación de videos. Que esté trabajado y dé mucho juego para crear"
    }
    """
    try:
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Transcripción:\n{texto_transcrito[:25000]}"}
            ],
            model="llama-3.3-70b-versatile", # MODELO ACTUALIZADO
            temperature=0.5,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        return {"resumen": "Error: " + str(e), "hilo_twitter": [], "linkedin": "", "tiktok_script": ""}

# --- RUTAS ---

@app.route('/')
def index():
    return render_template('index.html')
# --- FUNCIONALIDADES: SUBIR ARCHIVOS Y TRATAR ENLACES DE YOUTUBE ---
@app.route('/subir', methods=['POST'])
def subir_archivo():
    if 'file' not in request.files:
        return jsonify({"error": "No hay archivo"}), 400
    
    archivo = request.files['file']
    
    if archivo.filename == '':
        return jsonify({"error": "Nombre de archivo vacío"}), 400
        
    if not allowed_file(archivo.filename):
        return jsonify({"error": "Tipo de archivo no permitido"}), 400

    # Generamos nombre único
    ext = archivo.filename.rsplit('.', 1)[1].lower()
    nombre_unico = f"{uuid.uuid4()}.{ext}"
    ruta_temp = os.path.join("/tmp", nombre_unico)
    
    archivo.save(ruta_temp)
    
    try:
        # 1. Comprimir
        ruta_para_groq = comprimir_audio(ruta_temp)
        
        # 2. Transcribir
        texto = procesar_con_groq(ruta_para_groq)
        
        # Si la transcripción falla
        if isinstance(texto, str) and texto.startswith("Error"):
             return jsonify({"transcripcion": texto, "pack_viral": None})

        # 3. GENERAR PACK VIRAL (¡La Novedad!)
        print("--- GENERANDO PACK VIRAL PARA ARCHIVO SUBIDO ---")
        pack_social = generar_pack_viral(texto)
        
        # 4. Devolver todo junto
        return jsonify({
            "transcripcion": texto,
            "pack_viral": pack_social 
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
    finally:
        # Limpieza
        if os.path.exists(ruta_temp): os.remove(ruta_temp)
        if 'ruta_para_groq' in locals() and os.path.exists(ruta_para_groq) and ruta_para_groq != ruta_temp:
            os.remove(ruta_para_groq)
@app.route('/transformar', methods=['POST'])
def transformar():
    url = request.form.get('url')
    
    # SEGURIDAD 2: Nombre único también para YouTube
    # Usar hash(url) podría dar colisiones si dos usuarios piden el mismo video a la vez y uno borra el archivo del otro.
    # UUID es más seguro para concurrencia.
    nombre_original = f'/tmp/{uuid.uuid4()}.m4a'
    
    cookies_content = os.getenv("YT_COOKIES")
    cookie_path = "/tmp/cookies.txt"
    if cookies_content:
        with open(cookie_path, "w") as f:
            f.write(cookies_content)
    
    # ... (Configuración yt-dlp igual que antes) ...
    cache_dir = '/tmp/yt-dlp-cache'
    ydl_opts = {
        'verbose': True,
        'format': 'bestaudio/best',
        'outtmpl': nombre_original,
        'nocheckcertificate': True,
        'cookiefile': cookie_path if cookies_content else None,
        'remote_components': ['ejs:github'], 
        'socket_timeout': 30,
        'retries': 20,
        'fragment_retries': 20,
        'extractor_args': {
            'youtube': {
                'player_client': ['tv'], 
                'player_skip': ['web', 'web_music', 'android', 'ios']
            }
        },
        'js_runtimes': {'node': {}}
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        if not os.path.exists(nombre_original):
             return jsonify({"error": "Fallo en descarga"}), 500

        ruta_comprimida = comprimir_audio(nombre_original)
        texto_crudo = procesar_con_groq(ruta_comprimida)
        
        if isinstance(texto_crudo, str) and texto_crudo.startswith("Error"):
             return jsonify({"transcripcion": texto_crudo, "pack_viral": None})

        pack_social = generar_pack_viral(texto_crudo)
        
        return jsonify({
            "status": "success",
            "transcripcion": texto_crudo,
            "pack_viral": pack_social 
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
    finally:
        # LIMPIEZA SIEMPRE
        if os.path.exists(nombre_original): os.remove(nombre_original)
        if 'ruta_comprimida' in locals() and os.path.exists(ruta_comprimida) and ruta_comprimida != nombre_original:
            os.remove(ruta_comprimida)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 7860))
    app.run(host='0.0.0.0', port=port)
