from flask import Flask, render_template, request, jsonify
import yt_dlp
import os

app = Flask(__name__)

# --- NUEVA LÓGICA: Crear cookies.txt desde Variable de Entorno ---
cookie_content = os.environ.get('COOKIES_TXT_CONTENT')
if cookie_content:
    with open('cookies.txt', 'w', encoding='utf-8') as f:
        f.write(cookie_content)
    print("✅ Archivo cookies.txt generado exitosamente desde la variable de entorno.")
else:
    print("⚠️ Variable COOKIES_TXT_CONTENT no encontrada. Se intentará sin cookies.")
# ----------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    try:
        url = request.json.get('url')
        if not url:
            return jsonify({'error': 'URL requerida'}), 400
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'format': 'best[ext=mp4]',
            'socket_timeout': 45
        }

        # Verificamos si el archivo existe (creado antes) para añadirlo a la configuración
        if os.path.exists('cookies.txt'):
            ydl_opts['cookiefile'] = 'cookies.txt'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            videos = []
            audios = []

            if info.get('url'):
                videos.append({
                    'quality': info.get('format_note', 'Mejor Calidad'),
                    'url': info.get('url')
                })
            
            formats = info.get('formats', [])
            for f in formats:
                vcodec = f.get('vcodec') or 'none'
                acodec = f.get('acodec') or 'none'
                format_url = f.get('url')

                if not format_url:
                    continue

                if vcodec != 'none' and acodec != 'none':
                    if not any(v['url'] == format_url for v in videos):
                        videos.append({
                            'quality': f.get('format_note', 'Normal'),
                            'url': format_url
                        })
                elif acodec != 'none' and vcodec == 'none':
                    audios.append({
                        'quality': f.get('format_note', 'MP3'),
                        'url': format_url
                    })
            
        return jsonify({
            'videos': videos[:5],
            'audios': audios[:3],
            'title': info.get('title', 'Video')
        })
    
    except yt_dlp.utils.DownloadError as e:
        if "Sign in to confirm you’re not a bot" in str(e):
            return jsonify({'error': 'YouTube detectó un bloqueo anti-bot. Asegúrate de pegar el contenido de cookies.txt en la variable COOKIES_TXT_CONTENT de Render.'}), 200
        else:
            return jsonify({'error': f'Error de descarga de yt-dlp: {str(e)}'}), 200
    
    except Exception as e:
        return jsonify({'error': f'El servidor tardó demasiado o falló: {str(e)}'}), 200

if __name__ == '__main__':
    app.run(debug=True) 