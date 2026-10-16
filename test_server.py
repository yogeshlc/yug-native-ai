import importlib.util
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

spec = importlib.util.spec_from_file_location('yug', Path(__file__).with_name('server.py'))
yug = importlib.util.module_from_spec(spec)
spec.loader.exec_module(yug)

class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = yug.ThreadingHTTPServer(('127.0.0.1', 0), yug.Handler)
        cls.port = cls.server.server_address[1]
        yug.PORT = cls.port
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def call(self, path, body=None, origin=None):
        headers = {'Content-Type': 'application/json'}
        if origin: headers['Origin'] = origin
        request = Request(f'http://127.0.0.1:{self.port}' + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        try:
            with urlopen(request) as r: return r.status, r.read()
        except HTTPError as e: return e.code, e.read()

    def test_ui_and_assets(self):
        for path in ['/', '/app.js', '/style.css']:
            self.assertEqual(self.call(path)[0], 200)
        self.assertEqual(self.call('/../server.py')[0], 404)

    def test_discovery(self):
        with patch.object(yug, 'upstream', return_value={'models': [{'name': 'qwen3.5:35b'}]}):
            status, raw = self.call('/api/models/ollama')
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(raw)['models'], ['qwen3.5:35b'])

    def test_chat_and_image(self):
        body = {'model': 'qwen3.5:35b', 'messages': [{'role': 'user', 'content': 'Hello'}], 'image': 'data:image/png;base64,aGVsbG8='}
        with patch.object(yug, 'upstream', return_value={'message': {'content': 'Hello from model'}}) as upstream:
            status, raw = self.call('/api/chat', body)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(raw)['answer'], 'Hello from model')
            payload = upstream.call_args.args[2]
            self.assertEqual(payload['messages'][-1]['images'], ['aGVsbG8='])
            self.assertEqual(payload['options']['num_ctx'], 8192)
            self.assertFalse(payload['stream'])

    def test_compatible(self):
        with patch.dict(yug.PROVIDERS, {'compatible': {'url': 'http://localhost/v1', 'key': '', 'label': 'Test'}}):
            with patch.object(yug, 'upstream', return_value={'choices': [{'message': {'content': 'Compatible answer'}}]}) as upstream:
                status, raw = self.call('/api/chat', {'provider': 'compatible', 'model': 'test', 'messages': [{'role': 'user', 'content': 'Hi'}]})
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(raw)['answer'], 'Compatible answer')
                self.assertEqual(upstream.call_args.args[1], '/chat/completions')

    def test_rejected_and_offline(self):
        self.assertEqual(self.call('/api/chat', {'model': ''})[0], 400)
        self.assertEqual(self.call('/api/chat', {}, 'https://untrusted.example')[0], 403)
        with patch.object(yug, 'upstream', side_effect=yug.URLError('offline')):
            self.assertEqual(self.call('/api/models/ollama')[0], 503)
            self.assertEqual(self.call('/api/chat', {'model':'test', 'messages':[{'role':'user','content':'Hello'}]})[0],503)

if __name__ == '__main__': unittest.main()
