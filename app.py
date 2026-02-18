import os
import random
import json
import logging
import tempfile
import yt_dlp
import subprocess
from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify
from groq import Groq
import uuid

# ---------------------------------------------------------------------------
# CONFIGURACIÓN DE LOGGING
# Sustituye todos los print() por logging estructurado con niveles y timestamps.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# APP
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB

# ---------------------------------------------------------------------------
# CONSTANTES
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'm4a', 'mp4', 'mpeg', 'ogg', 'webm'}

DOMINIOS_YOUTUBE = {
    "youtube.com", "www.youtube.com",
    "youtu.be", "m.youtube.com",
    "music.youtube.com"
}
# ---------------------------------------------------------------------------
# FUNCIONES DE VALIDACIÓN
# ---------------------------------------------------------------------------

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def es_url_youtube_valida(url: str) -> bool:
    """
    Valida que la URL pertenece a YouTube antes de pasarla a yt-dlp.
    Sin esto, yt-dlp intentaría descargar cualquier URL que reciba,
    lo que es un vector de SSRF (Server-Side Request Forgery).
    """
    try:
        parsed = urlparse(url)
        # Debe tener esquema http/https y dominio conocido de YouTube
        return parsed.scheme in ("http", "https") and parsed.netloc in DOMINIOS_YOUTUBE
    except Exception:
        return False


# ---------------------------------------------------------------------------
# GESTIÓN DE API KEYS (sin cambios de lógica, solo logging mejorado)
# ---------------------------------------------------------------------------

def get_groq_client_with_fallback(intento: int = 0) -> Groq:
    """
    Rota entre las keys disponibles. En el primer intento elige una al azar
    para distribuir carga; en reintentos avanza linealmente por la lista.
    """
    keys_string = os.environ.get("GROQ_KEYS_LIST")

    if not keys_string:
        # Fallback a la key única por compatibilidad
        return Groq(api_key=os.environ.get("GROQ_API_KEY"))

    lista_keys = [k.strip() for k in keys_string.split(',') if k.strip()]
    if not lista_keys:
        raise ValueError("GROQ_KEYS_LIST está definida pero vacía.")

    indice = (random.randint(0, len(lista_keys) - 1) + intento) % len(lista_keys)
    api_key_actual = lista_keys[indice]
    log.info("Usando API KEY nº %d (termina en ...%s)", indice + 1, api_key_actual[-4:])
    return Groq(api_key=api_key_actual)


# ---------------------------------------------------------------------------
# COMPRESIÓN DE AUDIO
# ---------------------------------------------------------------------------

def comprimir_audio(ruta_original: str) -> str:
    """
    Convierte el audio a mono 16 kHz 32 kbps para reducir el tamaño
    antes de enviarlo a Groq. Devuelve la ruta del archivo comprimido,
    o la ruta original si la compresión falla.
    """
    # Guardamos el comprimido en el mismo directorio que el original
    directorio = os.path.dirname(ruta_original)
    nombre_comprimido = os.path.join(directorio, f"{uuid.uuid4()}_lite.mp3")

    log.info("Comprimiendo: %s → %s", ruta_original, nombre_comprimido)

    try:
        comando = [
            "ffmpeg", "-y", "-i", ruta_original,
            "-vn", "-ar", "16000", "-ac", "1", "-b:a", "32k",
            nombre_comprimido
        ]
        subprocess.run(
            comando,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return nombre_comprimido
    except subprocess.CalledProcessError as e:
        log.error("Error en compresión (ffmpeg): %s", e)
        return ruta_original
    except FileNotFoundError:
        log.error("ffmpeg no está instalado o no está en el PATH.")
        return ruta_original


# ---------------------------------------------------------------------------
# TRANSCRIPCIÓN CON GROQ
# ---------------------------------------------------------------------------

def procesar_con_groq(ruta_audio: str) -> str:
    """
    Envía el audio a Whisper a través de la API de Groq.
    Rota entre keys si recibe error 429.
    """
    MAX_REINTENTOS = 3

    for i in range(MAX_REINTENTOS):
        try:
            client = get_groq_client_with_fallback(intento=i)
            with open(ruta_audio, "rb") as f:
                transcripcion = client.audio.transcriptions.create(
                    file=(os.path.basename(ruta_audio), f.read()),
                    model="whisper-large-v3",
                    response_format="text",
                )
            log.info("Transcripción completada (intento %d).", i + 1)
            return transcripcion

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "Rate limit" in error_msg:
                log.warning("Key agotada (429). Cambiando... (intento %d/%d)", i + 1, MAX_REINTENTOS)
                continue
            else:
                log.error("Error inesperado en Groq: %s", error_msg)
                return f"Error en Groq: {error_msg}"

    return "Error: Todas las API Keys están agotadas. Vuelve en unos minutos."


# ---------------------------------------------------------------------------
# GENERACIÓN DE PACK VIRAL
# ---------------------------------------------------------------------------

# El prompt está aquí como constante, no enterrado dentro de la función,
# para que sea fácil de localizar y modificar sin tocar la lógica.
PROMPT_PACK_VIRAL = """
Eres un Editor Jefe experto en viralidad y en la juventud de hoy en día.
Tu objetivo es REEMPAQUETAR la transcripción para que esté completamente listo
para publicar en redes sociales.

REGLAS CRÍTICAS:
1. Responde SOLO con un JSON válido.
2. NO expliques nada antes ni después.

ESTRUCTURA JSON OBLIGATORIA:
{
    "resumen": "Empieza con 3 frases impactantes y directas si la transcripción es corta. A medida que vaya siendo más larga, añade más frases para cubrir todos los temas principales.",
    "hilo_twitter": ["Tweet 1 (Gancho)", "Tweet 2", "Tweet 3", "Tweet 4 (Cierre)"],
    "linkedin": "Texto profesional con negritas (**texto**) y emojis. Estructura: Gancho → Problema → Solución. Alarga según la extensión de la transcripción.",
    "tiktok_script": "Guion estructurado. Usa [VISUAL] y [AUDIO]. Gradúa el detalle según la transcripción."
}
"""

# Longitud máxima del texto que enviamos al LLM.
# Nota: el contenido se trunca silenciosamente; en el futuro sería
# buena idea avisar al usuario si su vídeo supera este límite.
MAX_CHARS_LLM = 22_000


def generar_pack_viral(texto_transcrito: str) -> dict:
    """
    Genera un pack de contenido para redes sociales a partir de la transcripción.
    Rota entre keys si recibe error 429. Normaliza las claves del JSON para
    absorber variaciones de nombres que devuelva el modelo.
    """
    MAX_REINTENTOS = 3

    for i in range(MAX_REINTENTOS):
        try:
            client = get_groq_client_with_fallback(intento=i)

            completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": PROMPT_PACK_VIRAL},
                    {"role": "user", "content": f"Transcripción:\n{texto_transcrito[:MAX_CHARS_LLM]}"}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.5,
                max_tokens=2048,
                response_format={"type": "json_object"}
            )

            contenido_bruto = completion.choices[0].message.content
            log.info("JSON recibido del LLM (intento %d): %.80s...", i + 1, contenido_bruto)

            data = json.loads(contenido_bruto)

            # Normalización de claves para absorber variaciones del modelo
            return {
                "resumen":      data.get("resumen")       or data.get("summary")          or "Resumen no generado.",
                "hilo_twitter": data.get("hilo_twitter")  or data.get("twitter_thread")   or [],
                "linkedin":     data.get("linkedin")      or data.get("linkedin_post")    or data.get("post_linkedin") or "Texto no generado.",
                "tiktok_script":data.get("tiktok_script") or data.get("tiktok")           or data.get("reels") or "Guion no generado."
            }

        except Exception as e:
            error_msg = str(e)
            log.warning("Error en intento %d: %s", i + 1, error_msg)

            if "429" in error_msg or "Rate limit" in error_msg:
                log.info("Cambiando de API Key por rate limit...")
                continue

            # Error no recuperable (JSON malformado, etc.)
            return {
                "resumen":       "Error técnico generando contenido.",
                "hilo_twitter":  ["Error"],
                "linkedin":      f"Error: {error_msg}",
                "tiktok_script": "Error"
            }

    return {
        "resumen":       "Servicio saturado. Todas las keys agotadas.",
        "hilo_twitter":  [],
        "linkedin":      "Vuelve en unos minutos.",
        "tiktok_script": ""
    }


# ---------------------------------------------------------------------------
# HELPERS DE LIMPIEZA
# ---------------------------------------------------------------------------

def limpiar_archivos(*rutas: str) -> None:
    """Elimina una lista de archivos temporales ignorando errores."""
    for ruta in rutas:
        if ruta and os.path.exists(ruta):
            try:
                os.remove(ruta)
                log.info("Archivo temporal eliminado: %s", ruta)
            except OSError as e:
                log.warning("No se pudo eliminar %s: %s", ruta, e)


# ---------------------------------------------------------------------------
# RUTAS
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/subir', methods=['POST'])
def subir_archivo():
    if 'file' not in request.files:
        return jsonify({"error": "No hay archivo en la petición."}), 400

    archivo = request.files['file']

    if not archivo.filename:
        return jsonify({"error": "Nombre de archivo vacío."}), 400

    if not allowed_file(archivo.filename):
        return jsonify({"error": f"Tipo de archivo no permitido. Formatos válidos: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    ext = archivo.filename.rsplit('.', 1)[1].lower()
    ruta_original = os.path.join("/tmp", f"{uuid.uuid4()}.{ext}")
    ruta_comprimida = None

    try:
        archivo.save(ruta_original)
        log.info("Archivo guardado en: %s", ruta_original)

        ruta_comprimida = comprimir_audio(ruta_original)
        texto = procesar_con_groq(ruta_comprimida)

        if isinstance(texto, str) and texto.startswith("Error"):
            return jsonify({"transcripcion": texto, "pack_viral": None})

        log.info("Generando pack viral para archivo subido...")
        pack_social = generar_pack_viral(texto)

        return jsonify({
            "transcripcion": texto,
            "pack_viral":    pack_social
        })

    except Exception as e:
        log.error("Error inesperado en /subir: %s", e, exc_info=True)
        return jsonify({"error": "Error interno del servidor."}), 500

    finally:
        # ruta_comprimida puede ser igual a ruta_original si la compresión falló;
        # limpiar_archivos deduplica automáticamente gracias al set
        archivos_a_limpiar = {ruta_original, ruta_comprimida} - {None}
        limpiar_archivos(*archivos_a_limpiar)


@app.route('/transformar', methods=['POST'])
def transformar():
    url = request.form.get('url', '').strip()

    if not url:
        return jsonify({"error": "No se proporcionó ninguna URL."}), 400

    # VALIDACIÓN DE URL — previene SSRF y uso indebido del endpoint
    if not es_url_youtube_valida(url):
        return jsonify({"error": "URL no válida. Solo se aceptan enlaces de YouTube."}), 400

    ruta_audio     = os.path.join("/tmp", f"{uuid.uuid4()}.m4a")
    ruta_comprimida = None
    ruta_cookies   = None

    # Gestión de cookies: archivo temporal por petición para evitar colisiones
    # entre peticiones concurrentes que compartan el mismo /tmp/cookies.txt
    cookies_content = os.environ.get("YT_COOKIES")
    if cookies_content:
        fd, ruta_cookies = tempfile.mkstemp(suffix=".txt", prefix="yt_cookies_", dir="/tmp")
        with os.fdopen(fd, 'w') as f:
            f.write(cookies_content)
        log.info("Cookies escritas en archivo temporal: %s", ruta_cookies)

    ydl_opts = {
        'verbose':            True,    # Mantener en True para poder depurar problemas de YouTube
        'format':             'bestaudio/best',
        'outtmpl':            ruta_audio,
        'force_ipv4': True,
        'source_address': '0.0.0.0',
        'nocheckcertificate': True,
        'cookiefile':         ruta_cookies,
        'socket_timeout':     30,
        'retries':            20,
        'fragment_retries':   20,
        'extractor_args': {
            'youtube': {
                'player_client': ['tv'],
                'player_skip':   ['web', 'web_music', 'android', 'ios']
            }
        },
        # js_runtimes es necesario para que yt-dlp use Node.js al resolver
        # el n-challenge de YouTube. Sin esto el solver no se invoca y
        # YouTube bloquea la descarga con "format not available".
        'js_runtimes': {'node': {}},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(ruta_audio):
            return jsonify({"error": "La descarga falló o el archivo no se generó."}), 500

        ruta_comprimida = comprimir_audio(ruta_audio)
        texto = procesar_con_groq(ruta_comprimida)

        if isinstance(texto, str) and texto.startswith("Error"):
            return jsonify({"transcripcion": texto, "pack_viral": None})

        log.info("Generando pack viral para vídeo de YouTube...")
        pack_social = generar_pack_viral(texto)

        return jsonify({
            "status":        "success",
            "transcripcion": texto,
            "pack_viral":    pack_social
        })

    except yt_dlp.utils.DownloadError as e:
        log.error("yt-dlp DownloadError: %s", e)
        return jsonify({"error": f"No se pudo descargar el vídeo: {str(e)}"}), 500

    except Exception as e:
        log.error("Error inesperado en /transformar: %s", e, exc_info=True)
        return jsonify({"error": "Error interno del servidor."}), 500

    finally:
        archivos_a_limpiar = {ruta_audio, ruta_comprimida, ruta_cookies} - {None}
        limpiar_archivos(*archivos_a_limpiar)


# ---------------------------------------------------------------------------
# ARRANQUE
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
