#!/bin/zsh
# Run from this project's folder, including when opened in Finder.
PROJECT_DIR="${0:A:h}"
cd "$PROJECT_DIR" || exit 1
PYTHON="$PROJECT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    print -u2 'The project virtual environment is missing. Install Wild-Locate first.'
    exit 1
fi
# macOS hidden flags prevent Python and Qt from discovering these files.
"$PYTHON" - <<'PY'
import os
from pathlib import Path
import stat
import sysconfig

site_packages = Path(sysconfig.get_path('purelib'))
paths = list(site_packages.glob('*.pth'))
plugins = site_packages / 'PyQt6' / 'Qt6' / 'plugins'
if plugins.exists():
    paths.extend([plugins, *plugins.rglob('*')])
for path in paths:
    flags = path.stat().st_flags
    if flags & stat.UF_HIDDEN:
        os.chflags(path, flags & ~stat.UF_HIDDEN)
PY
if [[ $? -ne 0 ]]; then
    print -u2 'Could not repair the Python or Qt file flags.'
    exit 1
fi
exec "$PYTHON" -m wildlocate
