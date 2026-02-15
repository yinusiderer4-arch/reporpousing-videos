import os
import whisper
import yt_dlp
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Cargamos el modelo Whisper (IA de transcripción)
# Usamos 'tiny' para que sea instantáneo o 'base' para más precisión
model = whisper.load_model("tiny")

def descargar_audio(url):
    # Recuperamos las cookies desde los secretos de Hugging Face
    cookies_content = os.getenv("YT_COOKIES")
    cookie_path = "/tmp/cookies.txt"
    
    if cookies_content:
        with open(cookie_path, "w") as f:
            f.write(cookies_content)

    nombre_archivo = f"/tmp/audio_{hash(url)}"
    
    ydl_opts = {
        'format': '140', # Solo audio m4a (el más ligero)
        'outtmpl': nombre_archivo,
        'cookiefile': cookie_path if cookies_content else None,
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
            return f"{nombre_archivo}.m4a"
        except Exception as e:
            print(f"Error de yt-dlp: {e}")
            return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/transformar', methods=['POST'])
def transformar():
    url = request.form.get('url')
    if not url:
        return jsonify({"error": "Falta la URL"}), 400

    ruta_audio = descargar_audio(url)
    
    if not ruta_audio or not os.path.exists(ruta_audio):
        return jsonify({"error": "YouTube bloqueó la conexión. Verifica las Cookies."}), 500

    try:
        # Transcripción con IA
        result = model.transcribe(ruta_audio)
        texto = result['text']
        
        # Limpieza
        os.remove(ruta_audio)
        
        return jsonify({"transcripcion": texto})
    except Exception as e:
        return jsonify({"error": f"Fallo en la IA: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)