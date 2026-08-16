from flask import Flask, render_template, request, jsonify
import yt_dlp

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    try:
        url = request.json.get('url')
        if not url:
            return jsonify({'error': 'URL requerida'}), 400
        
        # Simplificamos la configuración: 'best' busca el mejor formato que ya tenga video y audio combinados
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'format': 'best', 
            'socket_timeout': 30
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            videos = []
            audios = []

            # SOLUCIÓN 1: Capturar el enlace directo principal (Vital para TikTok e Instagram)
            if info.get('url'):
                videos.append({
                    'quality': info.get('format_note', 'Mejor Calidad'),
                    'url': info.get('url')
                })
            
            # SOLUCIÓN 2: Explorar la lista de formatos de forma segura (Para YouTube)
            formats = info.get('formats', [])
            for f in formats:
                # Aseguramos que no sean nulos antes de comparar
                vcodec = f.get('vcodec') or 'none'
                acodec = f.get('acodec') or 'none'

                # Buscamos formatos que tengan video y audio (pre-fusionados)
                if vcodec != 'none' and acodec != 'none':
                    # Evitamos duplicar el video principal que ya guardamos arriba
                    if not any(v['url'] == f.get('url') for v in videos):
                        videos.append({
                            'quality': f.get('format_note', 'Normal'),
                            'url': f.get('url')
                        })
                
                # Buscamos formatos que sean solo audio
                elif acodec != 'none' and vcodec == 'none':
                    audios.append({
                        'quality': f.get('format_note', 'MP3'),
                        'url': f.get('url')
                    })
            
        return jsonify({
            'videos': videos[:5],
            'audios': audios[:3],
            'title': info.get('title', 'Video')
        })
    
    except Exception as e:
        return jsonify({'error': f'Hubo un error interno: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True) 