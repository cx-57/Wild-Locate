import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

from wildlocate.cli import _configure_qt_runtime


@unittest.skipUnless(sys.platform == 'darwin', 'macOS plugin discovery')
class QtLaunchTests(unittest.TestCase):
    def test_hidden_plugin_is_made_discoverable(self):
        import PyQt6
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            platforms=root/'Qt6/plugins/platforms'
            platforms.mkdir(parents=True)
            plugin=platforms/'libqcocoa.dylib'
            plugin.write_bytes(b'test')
            for path in (root/'Qt6/plugins', platforms, plugin):
                os.chflags(path, path.stat().st_flags | stat.UF_HIDDEN)
            with patch.object(PyQt6, '__file__', str(root/'__init__.py')), patch.dict(os.environ):
                _configure_qt_runtime()
                self.assertEqual(os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'],str(platforms))
                for path in (root/'Qt6/plugins', platforms, plugin):
                    self.assertFalse(path.stat().st_flags & stat.UF_HIDDEN)

if __name__ == '__main__':
    unittest.main()
