from flask import Flask, render_template, request, jsonify
import yt_dlp
import os
import uuid
import threading
from time import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

app = Flask(__name__)

# --- Crear cookies.txt desde Variable de Entorno (igual que antes) ---
cookie_content = os.environ.get('COOKIES_TXT_CONTENT')
if cookie_content:
    with open('cookies.txt', 'w', encoding='utf-8') as f:
        f.write(cookie_content)
    print("✅ Archivo cookies.txt generado exitosamente desde la variable de entorno.")
else:
    print("⚠️ Variable COOKIES_TXT_CONTENT no encontrada. Se intentará sin cookies.")
# ----------------------------------------------------------------

# --- Almacén de jobs en memoria (se pierde si el dyno se reinicia) ---
jobs = {}

# --- Cache simple por URL (evita re-extraer videos repetidos) ---
cache = {}
CACHE_TTL = 300  # 5 minutos: las URLs directas de CDN expiran, no cachear más que esto

# --- Timeout duro para la extracción completa (no solo el socket) ---
EXTRACTION_TIMEOUT = 20  # segundos, deja margen dentro de la ventana de 30s de Render


def build_ydl_opts():
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'best[ext=mp4]/best',
        'socket_timeout': 8,
        'retries': 0,             # sin reintentos automáticos: si algo se cuelga, falla rápido
        'noplaylist': True,
        'skip_download': True,
        'extract_flat': False,
        'lazy_playlist': True,
        'concurrent_fragment_downloads': 1,
        'extractor_args': {
            'youtube': {
                'player_client': ['android'],   # cliente liviano, menos round-trips que 'web'
                'player_skip': ['configs'],
                'skip': ['dash', 'hls', 'translated_subs'],
            },
            'tiktok': {
                'api_hostname': 'api22-normal-c-useast2a.tiktokv.com',
            },
        },
    }
    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'
    return ydl_opts


def _do_extract(url):
    ydl_opts = build_ydl_opts()
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def extract_with_timeout(url, timeout=EXTRACTION_TIMEOUT):
    """Envuelve la extracción con un timeout duro controlado por nosotros,
    independiente de si yt-dlp respeta bien sus propios timeouts internos."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_do_extract, url)
        try:
            return future.result(timeout=timeout)
        except FutureTimeout:
            raise Exception('La extracción tardó demasiado. Intenta de nuevo o prueba otro video.')


def get_cached_or_extract(url):
    now = time()
    if url in cache:
        ts, data = cache[url]
        if now - ts < CACHE_TTL:
            return data
    data = extract_with_timeout(url)
    cache[url] = (now, data)
    return data


def format_response(info):
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

    return {
        'videos': videos[:5],
        'audios': audios[:3],
        'title': info.get('title', 'Video')
    }


def process_job(job_id, url):
    try:
        info = get_cached_or_extract(url)
        jobs[job_id] = {'status': 'done', 'data': format_response(info)}

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "Sign in to confirm you" in error_msg:
            msg = 'YouTube detectó un bloqueo anti-bot. Verifica las cookies.'
        elif "Requested format is not available" in error_msg:
            msg = 'No se encontró un MP4 directo para este video (los Shorts a veces fallan). Prueba con otro.'
        else:
            msg = f'Error de descarga: {error_msg}'
        jobs[job_id] = {'status': 'error', 'error': msg}

    except Exception as e:
        jobs[job_id] = {'status': 'error', 'error': str(e)}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/start-download', methods=['POST'])
def start_download():
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'URL requerida'}), 400

    job_id = str(uuid.uuid4())
    jobs[job_id] = {'status': 'processing'}

    thread = threading.Thread(target=process_job, args=(job_id, url), daemon=True)
    thread.start()

    return jsonify({'job_id': job_id})


@app.route('/status/<job_id>')
def check_status(job_id):
    job = jobs.get(job_id, {'status': 'not_found'})
    return jsonify(job)


if __name__ == '__main__':
    app.run(debug=True) 