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
    
    print("--- INICIO DIAGNÓSTICO DEL ENTORNO ---")
    
    # 1. ¿Dónde está Node?
    node_path = shutil.which('node')
    print(f"[CHECK] Ruta de Node: {node_path}")
    
    # 2. ¿Qué versión es?
    if node_path:
        try:
            ver = subprocess.getoutput(f"{node_path} --version")
            print(f"[CHECK] Versión de Node: {ver}")
        except Exception as e:
            print(f"[FAIL] Error obteniendo versión: {e}")

    # 3. ¿Puede Node encontrar sus módulos críticos?
    # Esto simula exactamente lo que intenta hacer el script de challenge
    try:
        # Intentamos importar jsdom y canvas desde python llamando a node
        check_cmd = [node_path, '-e', 'try { require("jsdom"); require("canvas"); console.log("SUCCESS"); } catch (e) { console.log("ERROR: " + e.message); process.exit(1); }']
        result = subprocess.run(check_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[CHECK] Módulos Node (jsdom/canvas): INSTALADOS Y ACCESIBLES ✅")
        else:
            print(f"[FAIL] Módulos Node: FALLO CRÍTICO ❌\nOutput: {result.stdout}\nError: {result.stderr}")
    except Exception as e:
        print(f"[FAIL] Error ejecutando prueba de módulos: {e}")

    # 4. Limpieza de Caché (VITAL para errores de challenge)
    # A veces yt-dlp recuerda que falló y no vuelve a intentar descargar el componente
    cache_dir = '/tmp/yt-dlp-cache'
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
        print("[CHECK] Caché de yt-dlp eliminada para forzar descarga de componentes.")
        
    print("--- FIN DIAGNÓSTICO ---")

    # --- CONFIGURACIÓN DE DESCARGA ---
    
    #cookies_content = os.getenv("YT_COOKIES")
    #cookie_path = "/tmp/cookies.txt"
    #if cookies_content:
        #with open(cookie_path, "w") as f:
            #f.write(cookies_content)
    # Creamos la variable AQUÍ para poder usarla después
    nombre_original = f'/tmp/audio_{hash(url)}.m4a'
    ydl_opts = {
        'verbose': True,
        'format': 'bestaudio/best',
        # AQUÍ USAMOS LA VARIABLE: Así yt-dlp guarda el archivo con ese nombre
        'outtmpl': nombre_original,
        
        'outtmpl': f'/tmp/audio_{hash(url)}.m4a',
        'nocheckcertificate': True,
        'cookiefile': None,
        'cachedir': cache_dir,
        # --- BLINDAJE CONTRA CORTES ---
        'socket_timeout': 30,      # Esperar hasta 30s si YouTube se pone lento
        'retries': 10,             # Reintentar 10 veces si falla un fragmento
        'fragment_retries': 10,    # Reintentar fragmentos específicos
        'ignoreerrors': False,     # Si hay error real, que pare (para no transcribir audios rotos)
        # --- LA CORRECCIÓN MAESTRA ---
        # 1. Va en la RAÍZ (no dentro de 'params').
        # 2. Es una LISTA ['...'] (no un string).
        # Esto le dice a yt-dlp: "Descarga el módulo EJS desde GitHub".
        'remote_components': ['ejs:github'], 
        
        'extractor_args': {
            'youtube': {
                # Solo TV (el único que funciona con cookies hoy en día)
                'player_client': ['android'],
                'player_skip': ['web', 'web_music', 'tv', 'ios']
            }
        },
        'js_runtimes': {'node': {}}
    }
    # --- NUEVO DEBUG: VERIFICACIÓN DE CONFIGURACIÓN ---
    print("\n--- VERIFICACIÓN DE CONFIGURACIÓN ---")
    # Imprimimos si la clave existe y qué valor tiene
    rc_val = ydl_opts.get('remote_components', 'NO CONFIGURADO ❌')
    print(f"[CONFIG] Remote Components: {rc_val}")
    
    if rc_val == ['ejs:github']:
        print("[CONFIG] ✅ La configuración parece correcta (Lista en raíz)")
    else:
        print("[CONFIG] ⚠️ CUIDADO: La configuración no coincide con lo esperado")
    print("--------------------------------------\n")
    try:
        # 4. DESCARGA
        print(f"--- INICIANDO DESCARGA EN: {nombre_original} ---")
        
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
