"""Render actual Qt widgets for layout review. Never runs a prediction."""

import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from web.app import MainWindow, create_application

app = create_application([])
window = MainWindow()
window.show()
app.processEvents()
target = Path(__file__).resolve().parents[1] / "artifacts"
target.mkdir(exist_ok=True)
window.grab().save(str(target / "desktop-initial.png"))
window.latitude.setText("north")
window.analyze()
app.processEvents()
window.grab().save(str(target / "desktop-validation.png"))
window.latitude.setText("42.3718")
window.resize(780, 740)
app.processEvents()
window.grab().save(str(target / "desktop-narrow.png"))
window.close()
print(f"Saved UI previews to {target}")
