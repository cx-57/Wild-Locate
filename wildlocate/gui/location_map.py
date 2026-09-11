import json
import math
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from wildlocate.gui.widgets import label

try:
    from PyQt6.QtWebChannel import QWebChannel
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
    from PyQt6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QWebEngineView = None

MAP_FILE = Path(__file__).with_name("map") / "index.html"


class MapBridge(QObject):
    ready = pyqtSignal()
    selected = pyqtSignal(float, float)
    tile_status = pyqtSignal(bool)

    @pyqtSlot()
    def mapReady(self):
        self.ready.emit()

    @pyqtSlot(float, float)
    def selectLocation(self, latitude, longitude):
        if math.isfinite(latitude) and math.isfinite(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180:
            self.selected.emit(latitude, longitude)

    @pyqtSlot(bool)
    def tilesAvailable(self, available):
        self.tile_status.emit(available)


if QWebEngineView is not None:
    class MapPage(QWebEnginePage):
        def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
            if url == QUrl.fromLocalFile(str(MAP_FILE)):
                return True
            if navigation_type == self.NavigationType.NavigationTypeLinkClicked and url.scheme() == "https":
                QDesktopServices.openUrl(url)
            return False


class LocationMap(QWidget):
    location_selected = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ready = False
        self._location = (42.3718, -72.2820)
        self.view = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        self.status = label("Loading map… Manual coordinates are also available below.", "small", True)
        if QWebEngineView is None:
            self.status.setText("Map unavailable. Install PyQt6-WebEngine to enable it, or enter coordinates below.")
            layout.addWidget(self.status)
            return

        self.profile = QWebEngineProfile("WildLocateMap", self)
        self.profile.setHttpUserAgent("Wild-Locate/1.0 (desktop habitat explorer)")
        self.profile.setHttpCacheMaximumSize(64 * 1024 * 1024)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
        self.view = QWebEngineView(self)
        self.view.setMinimumHeight(230)
        self.view.setAccessibleName("Location map. Click to choose a location, or enter coordinates below.")
        self.page = MapPage(self.profile, self.view)
        self.view.setPage(self.page)
        self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.channel = QWebChannel(self.page)
        self.bridge = MapBridge(self.channel)
        self.channel.registerObject("locationBridge", self.bridge)
        self.page.setWebChannel(self.channel)
        self.bridge.ready.connect(self.map_ready)
        self.bridge.selected.connect(self.select_location)
        self.bridge.tile_status.connect(self.tile_status)
        self.view.loadFinished.connect(self.loaded)
        self.view.renderProcessTerminated.connect(self.render_failed)
        layout.addWidget(self.view)
        layout.addWidget(self.status)
        self.view.setUrl(QUrl.fromLocalFile(str(MAP_FILE)))

    def map_ready(self):
        self._ready = True
        self.send_state()

    def loaded(self, ok):
        if not ok:
            self._ready = False
            self.status.setText("Map could not load. Enter coordinates below to continue.")

    def render_failed(self, *_):
        self.loaded(False)

    def tile_status(self, available):
        self.status.setText(
            "Click to place a pin. Drag to explore; use + / − to zoom."
            if available else
            "Map tiles are unavailable. Check your connection, or enter coordinates below."
        )

    def select_location(self, latitude, longitude):
        if self.isEnabled():
            self.location_selected.emit(latitude, longitude)

    def set_location(self, latitude=None, longitude=None, *, recenter=False):
        self._location = (latitude, longitude)
        self.send_state(recenter=recenter)

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self.send_state()

    def send_state(self, *, recenter=False):
        if self._ready:
            state = {"latitude": self._location[0], "longitude": self._location[1], "enabled": self.isEnabled(), "recenter": recenter}
            self.page.runJavaScript(f"window.setLocationState({json.dumps(state, allow_nan=False)});")

    def shutdown(self):
        if self.view is not None:
            from PyQt6 import sip
            self.view.stop()
            sip.delete(self.page)
            sip.delete(self.view)
            sip.delete(self.profile)
            self.view = None
            self._ready = False
