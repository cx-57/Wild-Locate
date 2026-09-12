from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class RegionalElevationRetryTests(unittest.TestCase):
    def test_elevation_download_recovers_after_three_transient_server_failures(self):
        from requests.exceptions import HTTPError
        from wildlocate.core.data.regional import _download_elevation_tile

        class FakeResponse:
            def __init__(self, status, content=b''):
                self.status_code = status
                self._content = content

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise HTTPError(f'{self.status_code} error')

            def iter_content(self, _size):
                yield self._content

        responses = [
            FakeResponse(502),
            FakeResponse(504),
            FakeResponse(502),
            FakeResponse(200, b'recovered-elevation'),
        ]

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'elevation.tif'
            with patch('wildlocate.core.data.regional.requests.get', side_effect=responses) as get, \
                 patch('wildlocate.core.data.regional.time.sleep') as sleep:
                _download_elevation_tile((1, 2, 3, 4), output)

            self.assertEqual(output.read_bytes(), b'recovered-elevation')
            self.assertEqual(get.call_count, 4)
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [2, 4, 8])


if __name__ == '__main__':
    unittest.main()
