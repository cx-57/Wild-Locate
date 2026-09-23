import http.client
import json
import sys
import threading
import time
import unittest
from unittest.mock import patch

from wildlocate.web.server import JobManager, create_server

PAYLOAD = {'species': 'Bobcat', 'latitude': 42.37, 'longitude': -72.28, 'region': 'MA', 'radius_km': 25}


class JobTests(unittest.TestCase):
    def manager(self, source):
        manager = JobManager(command=[sys.executable, '-c', source])
        self.addCleanup(manager.close)
        return manager

    def wait(self, manager, identifier):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = manager.status(identifier)
            if result['status'] != 'running':
                return result
            time.sleep(.01)
        self.fail('Worker did not complete')

    def test_success_and_error_protocol(self):
        for reply, expected in [({'result': {'score': .5}}, 'complete'), ({'error': 'Missing data', 'code': 'data_unavailable'}, 'error')]:
            m = self.manager(f'import json,sys; json.loads(sys.stdin.readline()); print({json.dumps(reply)!r})')
            job = m.start(PAYLOAD)
            result = self.wait(m, job['id'])
            self.assertEqual(result['status'], expected)
            self.assertEqual(result.get('result', {}).get('score') if expected == 'complete' else result['error'], .5 if expected == 'complete' else 'Missing data')

    def test_cancel_busy_restart_and_shutdown(self):
        m = self.manager('import json,sys,time; r=json.loads(sys.stdin.readline()); time.sleep(r.get("delay",0)); print(json.dumps({"result":{"score":.6}}))')
        first = m.start({'delay': 30})
        with self.assertRaises(ValueError):
            m.start({})
        self.assertEqual(m.cancel(first['id'])['status'], 'cancelled')
        second = m.start({})
        self.assertEqual(self.wait(m, second['id'])['result']['score'], .6)
        with self.assertRaises(KeyError):
            m.status(first['id'])
        m.close()
        with self.assertRaises(ValueError):
            m.start({})

    def test_bad_worker_output_is_error(self):
        m = self.manager('print("not JSON")')
        job = m.start({})
        self.assertEqual(self.wait(m, job['id'])['status'], 'error')


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.server = create_server(0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, method, path, payload=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        body = json.dumps(payload) if payload is not None else None
        h = {'Content-Type': 'application/json', 'X-Wildlocate-Token': self.server.token}
        h.update(headers or {})
        connection.request(method, path, body, h)
        response = connection.getresponse()
        data = response.read()
        status = response.status
        connection.close()
        return status, data

    def test_config_and_empty_states(self):
        status, data = self.request('GET', '/api/config')
        self.assertEqual(status, 200)
        config = json.loads(data)
        ma = next(r for r in config['regions'] if r['code'] == 'MA')
        self.assertIn('Bobcat', ma['species'])
        self.assertEqual(config['token'], self.server.token)

    def test_forbidden_requests_and_paths(self):
        self.assertEqual(self.request('POST', '/api/jobs', PAYLOAD, {'X-Wildlocate-Token': ''})[0], 403)
        self.assertEqual(self.request('POST', '/api/jobs', PAYLOAD, {'Origin': 'https://example.com'})[0], 403)
        self.assertEqual(self.request('GET', '/api/config', headers={'Host': 'evil.example'})[0], 403)
        for path in ('/../../pyproject.toml', '/%2e%2e/pyproject.toml', '/vendor/../../cli.py'):
            self.assertEqual(self.request('GET', path)[0], 404)

    def test_invalid_inputs_do_not_launch_jobs(self):
        with patch.object(self.server.jobs, 'start', side_effect=AssertionError('Invalid request reached worker')):
            for change in ({'latitude': True}, {'latitude': float('nan')}, {'longitude': 181}, {'radius_km': 11}, {'species': 'Unknown'}, {'region': 'NY'}, {'extra': 1}):
                self.assertEqual(self.request('POST', '/api/jobs', dict(PAYLOAD, **change))[0], 422)
            self.assertEqual(self.request('POST', '/api/jobs', ['wrong shape'])[0], 422)
            self.assertEqual(self.request('POST', '/api/jobs', {'padding': 'a' * 9000})[0], 413)

    def test_job_http_round_trip(self):
        self.server.jobs.close()
        self.server.jobs = JobManager(command=[sys.executable, '-c', 'import json,sys; r=json.loads(sys.stdin.readline()); print(json.dumps({"result":{"radius_km":r["radius_km"]}}))'])
        status, body = self.request('POST', '/api/jobs', PAYLOAD)
        self.assertEqual(status, 202)
        job = json.loads(body)
        for _ in range(100):
            status, body = self.request('GET', '/api/jobs/' + job['id'])
            result = json.loads(body)
            if result['status'] != 'running':
                break
            time.sleep(.01)
        self.assertEqual(result['result']['radius_km'], 25)

    def test_cli_preserves_desktop_and_dispatches_web(self):
        from wildlocate.cli import main
        with patch('sys.argv', ['wildlocate']), patch('wildlocate.cli.cmd_gui') as gui:
            main()
            gui.assert_called_once()
        with patch('sys.argv', ['wildlocate', 'web', '--port', '8766', '--no-browser']), patch('wildlocate.web.server.serve') as serve:
            main()
            serve.assert_called_once_with(port=8766, open_browser=False)
