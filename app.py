from flask import Flask, render_template, request, jsonify
import yt_dlp

app = Flask(__name__)
__author__ = "NARU"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'URL requerida'}), 400
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4'
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get('formats', [])
        
        videos = []
        audios = []
        for f in formats:
            if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                videos.append({
                    'quality': f.get('format_note', 'Desconocido'),
                    'url': f.get('url')
                })
            elif f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                audios.append({
                    'quality': f.get('format_note', 'MP3'),
                    'url': f.get('url')
                })
        
    return jsonify({
        'videos': videos[:5],
        'audios': audios[:3],
        'title': info.get('title', 'Video')
    })

if __name__ == '__main__':
    app.run(debug=True) 