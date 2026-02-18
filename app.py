import os
import random
import json
import yt_dlp
import subprocess
import uuid
import shutil
import tempfile  # PARA COOKIES SEGURAS
from urllib.parse import urlparse # PARA VALIDAR URLS
from flask import Flask, render_template, request, jsonify
from flask_limiter import Limiter # PARA RATE LIMITING
from flask_limiter.util import get_remote_address
from groq import Groq

app = Flask(__name__)

# --- CONFIGURACIÓN DE SEGURIDAD Y LÍMITES ---

# 1. RATE LIMITING: Protege tu API de abusos (5 peticiones por minuto por IP)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# 2. LÍMITE DE TAMAÑO DE ARCHIVO (500MB)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024 

# 3. DOMINIOS PERMITIDOS (Whitelist)
DOMINIOS_SEGUROS = [
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be",
    "twitter.com", "x.com", 
    "tiktok.com", "www.tiktok.com", "vm.tiktok.com",
    "instagram.com", "www.instagram.com"
]

ALLOWED_EXTENSIONS = {'mp3', 'wav', 'm4a', 'mp4', 'mpeg', 'ogg', 'webm'}

# 4. PROMPT DE SISTEMA (Configuración centralizada)
PROMPT_VIRAL_MARKETING = """
Eres un Editor Jefe experto en viralidad.
Tu objetivo es REEMPAQUETAR la transcripción para redes sociales.

REGLAS CRÍTICAS:
1. Responde SOLO con un JSON válido.
2. NO expliques nada antes ni después.

ESTRUCTURA JSON OBLIGATORIA:
{
    "resumen": "3 frases impactantes y directas.",
    "hilo_twitter": ["Tweet 1 (Gancho)", "Tweet 2", "Tweet 3", "Tweet 4 (Cierre)"], 
    "linkedin": "Texto profesional con negritas (**texto**) y emojis. Estructura: Gancho -> Problema -> Solución.",
    "tiktok_script": "Guion estructurado. Usa [VISUAL] y [AUDIO]."
}
"""

# --- FUNCIONES DE VALIDACIÓN ---

def es_url_segura(url):
    """Evita ataques SSRF validando que el dominio sea conocido."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Permitimos si el dominio termina en alguno de los permitidos
        # (ej: 'www.youtube.com' termina en 'youtube.com')
        return any(domain.endswith(permitido) for permitido in DOMINIOS_SEGUROS)
    except:
        return False

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- FUNCIONES AUXILIARES ---

def get_groq_client_with_fallback(intento=0):
    keys_string = os.environ.get("GROQ_KEYS_LIST") 
    if not keys_string:
        return Groq(api_key=os.environ.get("GROQ_API_KEY"))

    lista_keys = keys_string.split(',')
    indice = (random.randint(0, len(lista_keys)-1) + intento) % len(lista_keys)
    api_key_actual = lista_keys[indice].strip()
    
    print(f"--- 🔑 Usando API KEY nº {indice + 1} ({api_key_actual[-4:]}) ---")
    return Groq(api_key=api_key_actual)

def comprimir_audio(ruta_original):
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
    max_retries = 3 
    for i in range(max_retries):
        try:
            client = get_groq_client_with_fallback(intento=i)
            with open(ruta_audio, "rb") as file:
                transcription = client.audio.transcriptions.create(
                    file=(os.path.basename(ruta_audio), file.read()),
                    model="whisper-large-v3",
                    response_format="text",
                )
            return transcription 
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "Rate limit" in error_msg:
                print(f"⚠️ Key agotada. Rotando... ({i+1}/{max_retries})")
                continue 
            else:
                return f"Error en Groq: {error_msg}"
    return "Error: Todas las API Keys están agotadas. Vuelve mañana."

def generar_pack_viral(texto_transcrito):
    max_retries = 3 
    for i in range(max_retries):
        try:
            client = get_groq_client_with_fallback(intento=i)
            
            completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": PROMPT_VIRAL_MARKETING},
                    {"role": "user", "content": f"Transcripción:\n{texto_transcrito[:22000]}"}
                ],
                model="llama-3.3-70b-versatile", 
                temperature=0.5,
                max_tokens=2048, 
                response_format={"type": "json_object"}
            )
            
            contenido_bruto = completion.choices[0].message.content
            data = json.loads(contenido_bruto)
            
            # Normalización de claves (Cazador de errores)
            pack_seguro = {
                "resumen": data.get("resumen") or data.get("summary") or "Resumen no generado.",
                "hilo_twitter": data.get("hilo_twitter") or data.get("twitter_thread") or [],
                "linkedin": data.get("linkedin") or data.get("linkedin_post") or data.get("post_linkedin") or "Texto no generado.",
                "tiktok_script": data.get("tiktok_script") or data.get("tiktok") or data.get("reels") or "Guion no generado."
            }
            return pack_seguro 
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "Rate limit" in error_msg:
                continue 
            else:
                return {
                    "resumen": "Error técnico.",
                    "hilo_twitter": ["Error"],
                    "linkedin": f"Error: {str(e)}",
                    "tiktok_script": "Error"
                }
    return {
        "resumen": "Servicio saturado.",
        "hilo_twitter": [],
        "linkedin": "Vuelve mañana.",
        "tiktok_script": ""
    }

# --- RUTAS ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/subir', methods=['POST'])
@limiter.limit("5 per minute") # Rate Limit para subidas
def subir_archivo():
    ruta_temp = None
    ruta_para_groq = None
    
    try:
        if 'file' not in request.files: return jsonify({"error": "No hay archivo"}), 400
        archivo = request.files['file']
        if archivo.filename == '': return jsonify({"error": "Nombre vacío"}), 400
        if not allowed_file(archivo.filename): return jsonify({"error": "Archivo no permitido"}), 400

        ext = archivo.filename.rsplit('.', 1)[1].lower()
        nombre_unico = f"{uuid.uuid4()}.{ext}"
        ruta_temp = os.path.join("/tmp", nombre_unico)
        archivo.save(ruta_temp)
        
        ruta_para_groq = comprimir_audio(ruta_temp)
        texto = procesar_con_groq(ruta_para_groq)
        
        if isinstance(texto, str) and texto.startswith("Error"):
             return jsonify({"transcripcion": texto, "pack_viral": None})

        pack_social = generar_pack_viral(texto)
        return jsonify({"transcripcion": texto, "pack_viral": pack_social})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
    finally:
        # Limpieza robusta
        if ruta_temp and os.path.exists(ruta_temp): os.remove(ruta_temp)
        if ruta_para_groq and os.path.exists(ruta_para_groq) and ruta_para_groq != ruta_temp:
            os.remove(ruta_para_groq)


@app.route('/transformar', methods=['POST'])
@limiter.limit("5 per minute") # Rate Limit para descargas
def transformar():
    # Inicializamos variables para que el 'finally' no falle
    nombre_original = None
    ruta_comprimida = None
    temp_cookie_path = None
    
    try:
        url = request.form.get('url')
        if not url: return jsonify({"error": "Falta URL"}), 400
        
        # 1. SEGURIDAD: Validar Dominio
        if not es_url_segura(url):
            return jsonify({"error": "Dominio no permitido. Solo soportamos YouTube, Twitter, TikTok, etc."}), 403

        # 2. CONCURRENCIA: Cookies Seguras con tempfile
        cookies_content = os.getenv("YT_COOKIES")
        if cookies_content:
            # Creamos un archivo temporal que se borra al cerrar? 
            # No, mejor gestionarlo nosotros para pasárselo a yt-dlp por ruta
            temp_cookie = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt')
            temp_cookie.write(cookies_content)
            temp_cookie.close() # Cerramos para que yt-dlp pueda leerlo
            temp_cookie_path = temp_cookie.name
        
        nombre_original = f'/tmp/{uuid.uuid4()}.m4a'
        cache_dir = '/tmp/yt-dlp-cache'
        
        # 3. CONFIGURACIÓN LIMPIA DE YT-DLP
        ydl_opts = {
            'verbose': True,
            'format': 'bestaudio/best',
            'outtmpl': nombre_original,
            'nocheckcertificate': True,
            'cookiefile': temp_cookie_path, # Usamos la ruta temporal única
            'cachedir': cache_dir,
            'socket_timeout': 30,
            'retries': 20,
            'fragment_retries': 20,
            'extractor_args': {
                'youtube': {
                    'player_client': ['tv'], 
                    'player_skip': ['web', 'web_music', 'android', 'ios']
                }
            }
            # Eliminados remote_components y js_runtimes
        }

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
        # 4. LIMPIEZA ROBUSTA
        if nombre_original and os.path.exists(nombre_original): 
            os.remove(nombre_original)
        if ruta_comprimida and os.path.exists(ruta_comprimida) and ruta_comprimida != nombre_original:
            os.remove(ruta_comprimida)
        if temp_cookie_path and os.path.exists(temp_cookie_path):
            os.remove(temp_cookie_path) # Borramos el archivo de cookies temporal

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 7860))
    # Para desarrollo local con debug
    app.run(host='0.0.0.0', port=port)
