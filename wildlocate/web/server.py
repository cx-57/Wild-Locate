"""Loopback-only browser app, sharing the desktop prediction worker."""
import json
import math
import mimetypes
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from wildlocate.core.regions import REGIONS
from wildlocate.core.registry import available_species

ROOT = Path(__file__).resolve().parent
VENDOR = ROOT.parent / 'gui' / 'map' / 'vendor'
ASSETS = {'/': ROOT / 'index.html', '/style.css': ROOT / 'style.css', '/app.js': ROOT / 'app.js'}
for name in ('leaflet.js', 'leaflet.css'):
    ASSETS['/vendor/' + name] = VENDOR / name


class JobManager:
    def __init__(self, command=None):
        self.command = command or [sys.executable, '-u', '-m', 'wildlocate.core.worker', 'predict']
        self.lock = threading.Lock()
        self.job = None
        self.process = None
        self.closed = False

    def start(self, payload):
        with self.lock:
            if self.closed or (self.job and self.job['status'] == 'running'):
                raise ValueError('An analysis is already running or the server is stopping.')
            env = dict(os.environ)
            env['PYTHONPATH'] = os.pathsep.join(filter(None, (str(ROOT.parents[1]), env.get('PYTHONPATH'))))
            process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, env=env)
            job = {'id': uuid.uuid4().hex, 'status': 'running'}
            self.job, self.process = job, process
            threading.Thread(target=self._collect, args=(process, job, payload), daemon=True).start()
            return dict(job)

    def _collect(self, process, job, payload):
        try:
            stdout, stderr = process.communicate(json.dumps(payload, allow_nan=False) + '\n', timeout=1800)
            response = json.loads(stdout)
            if process.returncode or not isinstance(response, dict):
                raise ValueError('Worker failed')
            if 'error' in response:
                update = {'status': 'error', 'error': str(response['error'])}
            elif isinstance(response.get('result'), dict):
                # Ensure the HTTP result never contains NaN or infinity.
                json.dumps(response['result'], allow_nan=False)
                update = {'status': 'complete', 'result': response['result']}
            else:
                raise ValueError('Invalid worker response')
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            update = {'status': 'error', 'error': 'Analysis timed out. Try a smaller area.'}
        except Exception:
            update = {'status': 'error', 'error': 'The analysis process could not complete. Check your local models and environmental data.'}
        with self.lock:
            if self.job is job and job['status'] == 'running':
                job.update(update)

    def status(self, identifier):
        with self.lock:
            if not self.job or self.job['id'] != identifier:
                raise KeyError(identifier)
            return dict(self.job)

    def cancel(self, identifier):
        with self.lock:
            if not self.job or self.job['id'] != identifier:
                raise KeyError(identifier)
            if self.job['status'] == 'running':
                self.job['status'] = 'cancelled'
                self.process.kill()
                self.process.wait(timeout=10)
            return dict(self.job)

    def close(self):
        with self.lock:
            self.closed = True
            if self.process and self.process.poll() is None:
                self.job['status'] = 'cancelled'
                self.process.kill()
                self.process.wait(timeout=10)


def validate_request(payload):
    if not isinstance(payload, dict) or set(payload) - {'species', 'region', 'latitude', 'longitude', 'radius_km'}:
        raise ValueError('Supply species, state, latitude, longitude, and optionally radius.')
    region = payload.get('region', 'MA')
    if not isinstance(region, str) or region not in REGIONS:
        raise ValueError('Choose a supported state.')
    if payload.get('species') not in available_species(region):
        raise ValueError('Choose an available species for this state.')
    for key, limit in (('latitude', 90), ('longitude', 180)):
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not -limit <= value <= limit:
            raise ValueError(f'Enter a valid {key} between {-limit} and {limit}.')
    radius = payload.get('radius_km')
    if radius is not None and (isinstance(radius, bool) or radius not in (10, 25, 50)):
        raise ValueError('Choose a radius of 10, 25, or 50 km.')
    return dict(payload, region=region)


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def server_close(self):
        if hasattr(self, "jobs"):
            self.jobs.close()
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *_):
        pass

    def reply(self, status, value, content_type='application/json'):
        data = value if isinstance(value, bytes) else json.dumps(value, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://tile.openstreetmap.org; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def allowed(self, mutation=False):
        origin = self.server.origin
        if self.headers.get('Host') != origin.split('://')[1] or self.headers.get('Origin', origin) != origin:
            self.reply(403, {'error': 'Use the local URL printed by Wild-Locate.'})
            return False
        if mutation and not secrets.compare_digest(self.headers.get('X-Wildlocate-Token', ''), self.server.token):
            self.reply(403, {'error': 'Reload the page to reconnect to Wild-Locate.'})
            return False
        return True

    def do_GET(self):
        if not self.allowed():
            return
        path = urlsplit(self.path).path
        if path == '/api/config':
            self.reply(200, {'token': self.server.token, 'regions': [
                {'code': code, 'name': region.name, 'center': region.center, 'species': list(available_species(code))}
                for code, region in REGIONS.items()]})
        elif path.startswith('/api/jobs/'):
            try:
                self.reply(200, self.server.jobs.status(path.removeprefix('/api/jobs/')))
            except KeyError:
                self.reply(404, {'error': 'This analysis is no longer available. Start a new one.'})
        elif path in ASSETS and ASSETS[path].is_file():
            mime = mimetypes.guess_type(ASSETS[path].name)[0] or 'text/plain'
            self.reply(200, ASSETS[path].read_bytes(), mime + '; charset=utf-8')
        else:
            self.reply(404, {'error': 'Not found.'})

    def do_POST(self):
        if not self.allowed(mutation=True):
            return
        path = urlsplit(self.path).path
        if path != '/api/jobs' and not (path.startswith('/api/jobs/') and path.endswith('/cancel')):
            self.reply(404, {'error': 'Not found.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 0 or length > 8192:
                self.reply(413, {'error': 'Request is too large.'})
                return
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                self.reply(415, {'error': 'Send a JSON request.'})
                return
            raw = self.rfile.read(length)
            payload = json.loads(raw or b'{}')
            if path == '/api/jobs':
                payload = validate_request(payload)
                try:
                    job = self.server.jobs.start(payload)
                except ValueError as exc:
                    self.reply(409, {'error': str(exc)})
                    return
                self.reply(202, job)
            else:
                self.reply(200, self.server.jobs.cancel(path[len('/api/jobs/'):-len('/cancel')]))
        except (ValueError, TypeError, OverflowError) as exc:
            self.reply(422, {'error': str(exc) if not isinstance(exc, json.JSONDecodeError) else 'Send a valid JSON object.'})
        except KeyError:
            self.reply(404, {'error': 'Analysis not found.'})
        except OSError:
            self.reply(503, {'error': 'The analysis worker could not start. Try again.'})


def create_server(port=8765):
    if not 0 <= port <= 65535:
        raise ValueError('Port must be between 0 and 65535.')
    server = LocalServer(('127.0.0.1', port), Handler)
    server.token = secrets.token_urlsafe(32)
    server.jobs = JobManager()
    server.origin = f'http://127.0.0.1:{server.server_port}'
    return server


def serve(port=8765, open_browser=True):
    try:
        server = create_server(port)
    except (OSError, ValueError) as exc:
        raise SystemExit(f'Cannot start Wild-Locate: {exc}. Try --port 8766.') from exc
    print(f'Wild-Locate is running at {server.origin}\nPress Ctrl+C to stop.', flush=True)
    if open_browser:
        webbrowser.open(server.origin)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
