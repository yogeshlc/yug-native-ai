#!/usr/bin/env python3
"""Yug Native AI Framework: dependency-free, loopback-only AI gateway."""
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).parent
PORT = int(os.environ.get('YUG_PORT', '8787'))
PROVIDERS = {
    'ollama': {'label': 'Ollama · local', 'url': os.environ.get('YUG_OLLAMA_URL', 'http://127.0.0.1:11434'), 'key': ''},
}
if os.environ.get('YUG_COMPAT_URL'):
    PROVIDERS['compatible'] = {'label': 'Compatible API', 'url': os.environ['YUG_COMPAT_URL'].rstrip('/'), 'key': os.environ.get('YUG_COMPAT_KEY', '')}

def upstream(provider, route, payload=None):
    p = PROVIDERS[provider]
    headers = {'Content-Type': 'application/json'}
    if p['key']:
        headers['Authorization'] = 'Bearer ' + p['key']
    req = Request(p['url'].rstrip('/') + route,
                  data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
    with urlopen(req, timeout=600 if payload else 10) as response:
        return json.load(response)

def messages_for(body):
    history = body.get('messages', [])
    if not isinstance(history, list) or len(history) > 40:
        raise ValueError('Start a new chat after 20 exchanges.')
    result = [{'role': 'system', 'content': str(body.get('system', 'You are Yug, a helpful personal AI assistant.'))[:12000]}]
    for message in history:
        if not isinstance(message, dict) or message.get('role') not in ('user', 'assistant') or not isinstance(message.get('content'), str):
            raise ValueError('Invalid conversation.')
        result.append({'role': message['role'], 'content': message['content'][:100000]})
    if not history or history[-1]['role'] != 'user':
        raise ValueError('Enter a question.')
    return result

class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data):
        raw = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/providers':
            return self.reply(200, [{'id': k, 'label': v['label']} for k, v in PROVIDERS.items()])
        if path.startswith('/api/models/'):
            provider = path.rsplit('/', 1)[-1]
            if provider not in PROVIDERS:
                return self.reply(400, {'error': 'Unknown provider.'})
            try:
                data = upstream(provider, '/api/tags' if provider == 'ollama' else '/models')
                names = [m['name'] for m in data.get('models', [])] if provider == 'ollama' else [m['id'] for m in data.get('data', [])]
                return self.reply(200, {'models': names})
            except Exception:
                return self.reply(503, {'error': 'Cannot reach provider. Open Ollama and refresh models, or check the configured API URL.'})
        files = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
        if path not in files:
            return self.reply(404, {'error': 'Not found'})
        name, mime = files[path]
        raw = (ROOT / 'web' / name).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mime + '; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        if self.path != '/api/chat':
            return self.reply(404, {'error': 'Not found'})
        origin = self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{PORT}', f'http://localhost:{PORT}'):
            return self.reply(403, {'error': 'Origin rejected'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size < 1 or size > 12_000_000:
                raise ValueError('Request is too large or empty.')
            body = json.loads(self.rfile.read(size))
            provider = body.get('provider', 'ollama')
            if provider not in PROVIDERS:
                raise ValueError('Choose an available provider.')
            model = body.get('model')
            if not isinstance(model, str) or not model.strip():
                raise ValueError('Select a downloaded model.')
            messages = messages_for(body)
            image = body.get('image')
            if image:
                if not isinstance(image, str) or not image.startswith(('data:image/png;base64,', 'data:image/jpeg;base64,', 'data:image/webp;base64,')):
                    raise ValueError('Use a PNG, JPEG or WebP image.')
                if provider == 'ollama':
                    messages[-1]['images'] = [image.split(',', 1)[1]]
                else:
                    text = messages[-1]['content']
                    messages[-1]['content'] = [{'type': 'text', 'text': text}, {'type': 'image_url', 'image_url': {'url': image}}]
            payload = {'model': model, 'messages': messages, 'stream': False}
            if provider == 'ollama':
                payload['options'] = {'num_ctx': 8192}
            data = upstream(provider, '/api/chat' if provider == 'ollama' else '/chat/completions', payload)
            answer = data.get('message', {}).get('content', '') if provider == 'ollama' else data['choices'][0]['message'].get('content', '')
            self.reply(200, {'answer': answer or 'The model returned no text. Try a different model or shorter question.'})
        except (ValueError, TypeError, KeyError) as exc:
            self.reply(400, {'error': str(exc)})
        except HTTPError as exc:
            self.reply(502, {'error': f'Provider returned HTTP {exc.code}. Check the model, credentials and image support.'})
        except (URLError, TimeoutError, OSError):
            self.reply(503, {'error': 'Provider unavailable or timed out. Ensure Ollama is running and the model fits in memory.'})
        except Exception:
            self.reply(502, {'error': 'Unexpected provider response. Check provider compatibility.'})

if __name__ == '__main__':
    print(f'Yug Native AI Framework → http://127.0.0.1:{PORT}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
