import os
import random
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
def get_groq_client_with_fallback(intento=0):
    """
    Intenta obtener un cliente con una Key que funcione.
    Si falla, prueba la siguiente.
    """
    # Obtenemos la lista de keys de las variables de entorno
    keys_string = os.environ.get("GROQ_KEYS_LIST") 
    
    # Si no hay lista, usamos la key única de siempre por compatibilidad
    if not keys_string:
        return Groq(api_key=os.environ.get("GROQ_API_KEY"))

    lista_keys = keys_string.split(',')
    
    # Selección inteligente: 
    # Si es el primer intento, pilla una al azar para distribuir la carga.
    # Si es un reintento (intento > 0), pilla la siguiente en la lista.
    indice = (random.randint(0, len(lista_keys)-1) + intento) % len(lista_keys)
    api_key_actual = lista_keys[indice].strip()
    
    print(f"--- 🔑 Usando API KEY nº {indice + 1} (Finaliza en ...{api_key_actual[-4:]}) ---")
    return Groq(api_key=api_key_actual)
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
    max_retries = 3 # Intentaremos con hasta 3 keys distintas
    
    for i in range(max_retries):
        try:
            client = get_groq_client_with_fallback(intento=i)
            
            with open(ruta_audio, "rb") as file:
                transcription = client.audio.transcriptions.create(
                    file=(os.path.basename(ruta_audio), file.read()),
                    model="whisper-large-v3",
                    response_format="text",
                )
            return transcription # ¡Éxito!
            
        except Exception as e:
            error_msg = str(e)
            # Solo reintentamos si es error de LÍMITE (429)
            if "429" in error_msg or "Rate limit" in error_msg:
                print(f"⚠️ Key agotada. Cambiando a la siguiente... (Intento {i+1}/{max_retries})")
                continue # Pasa a la siguiente vuelta del bucle (siguiente key)
            else:
                # Si es otro error (archivo corrupto, etc), fallamos de verdad
                return f"Error en Groq: {error_msg}"
    
    return "Error: Todas las API Keys están agotadas. Vuelve mañana."

def generar_pack_viral(texto_transcrito):
    """Genera contenido viral con Llama 3.3 asegurando que completa el JSON."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key: return {"error": "Falta API Key"}

    client = Groq(api_key=api_key)
    
    # CAMBIO 1: Prompt optimizado para que no se agote antes de acabar
    prompt = """
    Eres un Editor Jefe experto en viralidad.
    Tu objetivo es REEMPAQUETAR la transcripción para redes sociales.
    
    REGLAS CRÍTICAS:
    1. Responde SOLO con un JSON válido.
    2. NO expliques nada antes ni después.
    3. Asegúrate de cerrar todas las llaves y comillas.
    
    ESTRUCTURA JSON OBLIGATORIA:
    {
        "resumen": "3 frases impactantes y directas.",
        "hilo_twitter": ["Tweet 1 (Gancho)", "Tweet 2", "Tweet 3", "Tweet 4 (Cierre)"], 
        "linkedin": "Texto profesional con negritas (**texto**) y emojis. Estructura: Gancho -> Problema -> Solución.",
        "tiktok_script": "Guion estructurado. Usa [VISUAL] para la imagen y [AUDIO] para la voz."
    }
    """
    # Nota: He bajado el hilo a 4 tweets para asegurar que queda espacio para LinkedIn y TikTok.

    try:
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt},
                # Recortamos un poco más la entrada para dejar más espacio a la salida
                {"role": "user", "content": f"Transcripción:\n{texto_transcrito[:22000]}"}
            ],
            model="llama-3.3-70b-versatile", 
            temperature=0.5,
            max_tokens=2048, # Forzamos espacio suficiente para la respuesta
            response_format={"type": "json_object"}
        )
        
        contenido_bruto = completion.choices[0].message.content
        print(f"--- RESPUESTA JSON RAW ---\n{contenido_bruto[:100]}... (y el final) ...{contenido_bruto[-100:]}\n--------------------------")
        
        data = json.loads(contenido_bruto)
        
        # CAMBIO 2: Normalización de Claves (El Cazador)
        # A veces la IA llama a "linkedin" como "post_linkedin" o "linkedin_text". Esto lo arregla.
        pack_seguro = {
            "resumen": data.get("resumen") or data.get("summary") or "Resumen no generado.",
            
            "hilo_twitter": data.get("hilo_twitter") or data.get("twitter_thread") or [],
            
            # Buscamos variantes para LinkedIn
            "linkedin": data.get("linkedin") or data.get("linkedin_post") or data.get("post_linkedin") or "Texto de LinkedIn no generado.",
            
            # Buscamos variantes para TikTok
            "tiktok_script": data.get("tiktok_script") or data.get("tiktok") or data.get("reels") or "Guion no generado."
        }
        
        return pack_seguro
        
    except Exception as e:
        print(f"❌ ERROR JSON PACK VIRAL: {e}")
        return {
            "resumen": "Error al generar contenido viral.",
            "hilo_twitter": ["Error"],
            "linkedin": f"Hubo un error técnico generando este texto: {str(e)}",
            "tiktok_script": "Inténtalo de nuevo."
        }
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
