"""Launch with python -m web.app or python web/app.py."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import time

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtCore import QIODevice, QSaveFile, Qt, QTimer
from PyQt6.QtGui import QFont, QFontDatabase, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QBoxLayout, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLineEdit, QMainWindow, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from src.catalog import SUPPORTED_SPECIES
from web.client import PredictionClient
from web.formatting import coordinates, feature_display, ordinal
from web.theme import STYLESHEET
from web.widgets import BrandMark, ContourArt, Disclosure, SpeciesCombo, SuitabilityGauge, app_icon, divider, label


def button(text, role="", callback=None):
    widget = QPushButton(text)
    widget.setObjectName(role)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if callback:
        widget.clicked.connect(callback)
    return widget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wild-Locate · Habitat Explorer")
        self.setWindowIcon(app_icon())
        self.resize(1240, 930)
        self.setMinimumSize(760, 640)
        self.result = None
        self.client = PredictionClient(self)
        self.client.succeeded.connect(self._show_result)
        self.client.failed.connect(self._show_error)
        self.client.cancelled.connect(self._cancelled)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._update_elapsed)
        self._started_at = 0

        shell = QWidget()
        shell.setObjectName("canvas")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(self._build_nav())
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        canvas = QWidget()
        canvas.setObjectName("canvas")
        outer = QHBoxLayout(canvas)
        outer.setContentsMargins(36, 0, 36, 0)
        self.page = QWidget()
        self.page.setObjectName("page")
        self.page.setMaximumWidth(1220)
        self.page_layout = QVBoxLayout(self.page)
        self.page_layout.setContentsMargins(0, 0, 0, 24)
        self.page_layout.setSpacing(20)
        self.page_layout.addWidget(self._build_hero())

        self.cards = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.cards.setSpacing(22)
        self.input_card = self._build_inputs()
        self.result_card = self._build_results()
        self.cards.addWidget(self.input_card, 0)
        self.cards.addWidget(self.result_card, 1)
        self.page_layout.addLayout(self.cards)

        self.environment = Disclosure("Environmental Conditions")
        self.environment.body_layout.addWidget(label("Measured conditions at the selected location. These values do not indicate each feature's contribution to the score.", "muted", True))
        self.feature_table = QGridLayout()
        self.feature_table.setHorizontalSpacing(24)
        self.feature_table.setVerticalSpacing(12)
        self.environment.body_layout.addLayout(self.feature_table)
        self.page_layout.addWidget(self.environment)
        self.environment.hide()
        self.methodology = self._build_methodology()
        self.page_layout.addWidget(self.methodology)

        footer = QHBoxLayout()
        footer.addWidget(label("WILD-LOCATE   /   A closer look at habitat.", "small"))
        footer.addStretch()
        footer.addWidget(label("Built on observations. Informed by environment.", "small"))
        self.page_layout.addLayout(footer)
        self.page_layout.addStretch()
        outer.addWidget(self.page)
        self.scroll.setWidget(canvas)
        shell_layout.addWidget(self.scroll)
        self.setCentralWidget(shell)
        self._responsive_layout()

        self.species.currentTextChanged.connect(self._inputs_changed)
        for field in (self.latitude, self.longitude):
            field.textChanged.connect(self._inputs_changed)
            field.returnPressed.connect(self.analyze)
        self.shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.shortcut.activated.connect(self.analyze)
        self.cancel_shortcut = QShortcut(QKeySequence("Escape"), self)
        self.cancel_shortcut.activated.connect(self._cancel_if_busy)
        self.setTabOrder(self.species, self.latitude)
        self.setTabOrder(self.latitude, self.longitude)
        self.setTabOrder(self.longitude, self.analyze_button)
        self.species.setFocus(Qt.FocusReason.OtherFocusReason)

    def _build_nav(self):
        nav = QWidget()
        nav.setObjectName("nav")
        row = QHBoxLayout(nav)
        row.setContentsMargins(38, 0, 38, 0)
        row.setSpacing(13)
        row.addWidget(BrandMark())
        row.addWidget(label("Wild-Locate", "brand"))
        row.addSpacing(35)
        row.addWidget(button("Habitat explorer", "navActive", self._go_top))
        row.addWidget(button("How it works", callback=self._show_methodology))
        row.addStretch()
        row.addWidget(label("MASSACHUSETTS", "pill"), 0, Qt.AlignmentFlag.AlignVCenter)
        nav.setFixedHeight(76)
        return nav

    def _build_hero(self):
        hero = QWidget()
        row = QHBoxLayout(hero)
        row.setContentsMargins(0, 32, 0, 8)
        text = QVBoxLayout()
        text.setSpacing(12)
        text.addWidget(label("WILDLIFE  /  HABITAT INTELLIGENCE", "eyebrow"))
        text.addWidget(label("Find where wildlife can thrive.", "hero", True))
        description = label("Wild-Locate uses species observations and environmental data to estimate how suitable a location is as habitat for wildlife.", "description", True)
        text.addWidget(description)
        row.addLayout(text, 1)
        self.hero_art = ContourArt(compact=True)
        self.hero_art.setFixedWidth(220)
        row.addWidget(self.hero_art)
        return hero

    def _build_inputs(self):
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(26, 25, 26, 25)
        layout.setSpacing(15)
        layout.addWidget(label("Explore a location", "heading"))
        layout.addWidget(label("One species. One place. A new perspective.", "muted", True))
        layout.addSpacing(3)
        layout.addWidget(label("01   SELECT A SPECIES", "step"))
        self.species = SpeciesCombo()
        self.species.addItems(SUPPORTED_SPECIES)
        self.species.setCurrentText("North American River Otter")
        self.species.setAccessibleName("Species")
        self.species.setMaxVisibleItems(5)
        layout.addWidget(self.species)
        layout.addSpacing(3)
        layout.addWidget(label("02   CHOOSE A LOCATION", "step"))
        coordinate_layout = QHBoxLayout()
        coordinate_layout.setSpacing(12)
        self.latitude = QLineEdit("42.3718")
        self.longitude = QLineEdit("-72.2820")
        for name, field, placeholder in (("Latitude", self.latitude, "e.g. 42.3718"), ("Longitude", self.longitude, "e.g. -72.2820")):
            column = QVBoxLayout()
            column.setSpacing(7)
            caption = label(name, "fieldLabel")
            caption.setBuddy(field)
            field.setAccessibleName(name)
            field.setPlaceholderText(placeholder)
            field.setMinimumWidth(0)
            field.setMaxLength(24)
            field.setToolTip(f"{name} in decimal degrees (WGS 84)")
            column.addWidget(caption)
            column.addWidget(field)
            coordinate_layout.addLayout(column, 1)
        layout.addLayout(coordinate_layout)
        layout.addWidget(label("Decimal degrees · available Massachusetts data", "small", True))
        self.example_button = button("↗  Use example coordinates", "link", self._use_example)
        self.example_button.setToolTip("Fills an example location. Select Analyze Habitat to get a real prediction.")
        layout.addWidget(self.example_button)
        self.error = label("", "error", True)
        self.error.setAccessibleName("Analysis error")
        layout.addWidget(self.error)
        self.error.hide()
        layout.addStretch(1)
        self.analyze_button = button("Analyze Habitat   →", "primary", self.analyze)
        self.analyze_button.setToolTip("Analyze the selected species and location (Ctrl+Enter)")
        layout.addWidget(self.analyze_button)
        self.cancel_button = button("Cancel analysis", "secondary", self.client.cancel)
        layout.addWidget(self.cancel_button)
        self.cancel_button.hide()
        self.input_note = label("Your analysis runs locally on this computer.", "small", True)
        self.input_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.input_note)
        return card

    def _build_results(self):
        card = QFrame()
        card.setObjectName("card")
        card.setMinimumHeight(474)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(12)
        row = QHBoxLayout()
        row.addWidget(label("HABITAT ASSESSMENT", "eyebrow"))
        row.addStretch()
        self.result_status = label("AWAITING ANALYSIS", "small")
        row.addWidget(self.result_status)
        layout.addLayout(row)
        self.stack = QStackedWidget()
        self.empty_page = QWidget()
        empty_layout = QVBoxLayout(self.empty_page)
        empty_layout.setContentsMargins(12, 10, 12, 0)
        empty_layout.setSpacing(14)
        empty_layout.addStretch()
        empty_layout.addWidget(ContourArt())
        heading = label("A landscape of possibility.", "emptyHeading", True)
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(heading)
        self.empty_text = label("Choose a species and a location to discover how the surrounding habitat compares.", "muted", True)
        self.empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_text.setFixedWidth(390)
        self.empty_text.setMinimumHeight(48)
        empty_layout.addWidget(self.empty_text, 0, Qt.AlignmentFlag.AlignHCenter)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setMaximumWidth(240)
        self.progress.setAccessibleName("Habitat analysis in progress")
        empty_layout.addWidget(self.progress, 0, Qt.AlignmentFlag.AlignHCenter)
        self.progress.hide()
        self.elapsed = label("", "small")
        self.elapsed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.elapsed)
        empty_layout.addStretch()
        self.stack.addWidget(self.empty_page)

        self.result_page = QWidget()
        result_layout = QVBoxLayout(self.result_page)
        result_layout.setContentsMargins(0, 9, 0, 0)
        result_layout.setSpacing(10)
        self.result_species = label("", "heading", True)
        self.result_location = label("", "muted")
        self.result_location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        result_layout.addWidget(self.result_species)
        result_layout.addWidget(self.result_location)
        result_layout.addSpacing(5)
        self.category = label("", "category")
        result_layout.addWidget(self.category, 0, Qt.AlignmentFlag.AlignLeft)
        number_row = QHBoxLayout()
        self.percentile = label("", "percentile")
        number_row.addWidget(self.percentile)
        number_row.addWidget(label("percentile", "description"), 0, Qt.AlignmentFlag.AlignBottom)
        number_row.addStretch()
        result_layout.addLayout(number_row)
        self.gauge = SuitabilityGauge()
        result_layout.addWidget(self.gauge)
        self.interpretation = label("", "muted", True)
        result_layout.addWidget(self.interpretation)
        result_layout.addSpacing(5)
        result_layout.addWidget(divider())
        metadata = QHBoxLayout()
        metadata.setSpacing(18)
        self.score = label("", "subheading")
        self.model = label("", "subheading", True)
        self.observations = label("", "subheading")
        for caption, value in (("Relative suitability score", self.score), ("Model", self.model), ("Training observations", self.observations)):
            column = QVBoxLayout()
            column.setSpacing(5)
            column.addWidget(label(caption, "small", True))
            column.addWidget(value)
            metadata.addLayout(column, 1)
        result_layout.addLayout(metadata)
        self.stack.addWidget(self.result_page)
        layout.addWidget(self.stack, 1)
        layout.addWidget(label("The suitability score is relative and does not represent the probability that the species is currently present.", "notice", True))
        self.export_button = button("↓  Export assessment as JSON", "link", self._export_result)
        self.export_button.hide()
        layout.addWidget(self.export_button)
        return card

    def _build_methodology(self):
        info = Disclosure("Behind the assessment", "methodology")
        info.body_layout.addWidget(label("The existing species-specific machine-learning model combines iNaturalist species observations with environmental conditions at your selected location.", "muted", True))
        grid = QGridLayout()
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(16)
        entries = (
            ("01 / Observations", "iNaturalist species observations used in model training."),
            ("02 / Land & terrain", "NLCD land cover and impervious surface; USGS elevation and derived terrain conditions."),
            ("03 / Water & roads", "Massachusetts hydrography and road data describe proximity to water and roads."),
            ("04 / Relative suitability", "Percentiles compare this location's score with the species' comparison locations. They are not a measure of model confidence."),
        )
        for index, (title, description) in enumerate(entries):
            column = QVBoxLayout()
            column.setSpacing(7)
            column.addWidget(label(title, "fieldLabel"))
            column.addWidget(label(description, "muted", True))
            grid.addLayout(column, index // 2, index % 2)
        info.body_layout.addLayout(grid)
        info.body_layout.addWidget(label("Percentile guide: 0–19 Very Low · 20–39 Low · 40–59 Moderate · 60–79 High · 80–100 Very High", "small", True))
        return info

    def _go_top(self):
        if hasattr(self, "scroll"):
            self.scroll.verticalScrollBar().setValue(0)

    def _show_methodology(self):
        self.methodology.set_expanded(True)
        QTimer.singleShot(0, lambda: self.scroll.ensureWidgetVisible(self.methodology))

    def _responsive_layout(self):
        narrow = self.width() < 1000
        self.cards.setDirection(QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight)
        self.input_card.setMinimumWidth(0 if narrow else 330)
        self.input_card.setMaximumWidth(16777215 if narrow else 355)
        self.hero_art.setVisible(not narrow)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "cards"):
            self._responsive_layout()

    def _use_example(self):
        lat, lon = (42.28, -71.35) if self.species.currentText() == "Red Fox" else (42.3718, -72.2820)
        self.latitude.setText(f"{lat:.4f}")
        self.longitude.setText(f"{lon:.4f}")
        self.input_note.setText("Example coordinates loaded. Ready to analyze.")

    def _inputs_changed(self):
        self.error.hide()
        for field in (self.latitude, self.longitude):
            field.setProperty("invalid", False)
            field.style().unpolish(field)
            field.style().polish(field)
        if self.result is not None:
            self.result = None
            self.stack.setCurrentWidget(self.empty_page)
            self.environment.hide()
            self.export_button.hide()
            self.empty_text.setText("Your selection has changed. Analyze this location to see a new assessment.")
            self.result_status.setText("AWAITING ANALYSIS")
        self.input_note.setText("Your analysis runs locally on this computer.")

    def _read_coordinates(self):
        values = []
        errors = []
        first_invalid = None
        for name, field, limit in (("Latitude", self.latitude, 90), ("Longitude", self.longitude, 180)):
            try:
                value = float(field.text().strip())
                if not math.isfinite(value) or not -limit <= value <= limit:
                    raise ValueError
                values.append(value)
            except ValueError:
                field.setProperty("invalid", True)
                field.style().unpolish(field)
                field.style().polish(field)
                errors.append(f"{name} must be a number between −{limit} and {limit}.")
                first_invalid = first_invalid or field
        if errors:
            self.error.setText("\n".join(errors))
            self.error.show()
            first_invalid.setFocus()
            return None
        return values

    def analyze(self):
        if self.client.busy:
            return
        values = self._read_coordinates()
        if values is None:
            return
        self.error.hide()
        self.result = None
        self.environment.hide()
        self.export_button.hide()
        self.stack.setCurrentWidget(self.empty_page)
        self.empty_text.setText("Reading local environmental data and evaluating the species model.")
        self.result_status.setText("ANALYSIS IN PROGRESS")
        self._set_busy(True)
        self._started_at = time.monotonic()
        self._update_elapsed()
        self.timer.start()
        self.client.analyze(self.species.currentText(), *values)

    def _set_busy(self, busy: bool):
        for widget in (self.species, self.latitude, self.longitude, self.example_button, self.analyze_button):
            widget.setEnabled(not busy)
        self.cancel_button.setVisible(busy)
        self.progress.setVisible(busy)
        self.analyze_button.setText("Analyzing habitat…" if busy else "Analyze Habitat   →")
        if not busy:
            self.timer.stop()
            self.elapsed.setText("")

    def _update_elapsed(self):
        seconds = int(time.monotonic() - self._started_at)
        self.elapsed.setText(f"{seconds}s elapsed · first analysis may take longer")

    def _show_result(self, result: dict):
        self._set_busy(False)
        self.result = result
        self.result_species.setText(result["species"])
        self.result_location.setText(coordinates(result["latitude"], result["longitude"]))
        self.category.setText(f"{result['category'].upper()} HABITAT SUITABILITY")
        self.percentile.setText(ordinal(result["percentile"]))
        self.gauge.set_percentile(result["percentile"])
        self.interpretation.setText(f"This location received a higher habitat-suitability score than approximately {result['percentile']}% of comparison locations for this species.")
        self.score.setText(f"{result['score']:.3f}")
        self.model.setText(result["model"])
        self.observations.setText(f"{result['training_observations']:,}")
        self.result_status.setText("ASSESSMENT COMPLETE")
        self.stack.setCurrentWidget(self.result_page)
        while self.feature_table.count():
            item = self.feature_table.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for row, (name, value) in enumerate(result["features"].items()):
            title, formatted = feature_display(name, value)
            self.feature_table.addWidget(label(title, "muted", True), row, 0)
            value_label = label(formatted, "fieldLabel")
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.feature_table.addWidget(value_label, row, 1)
        self.feature_table.setColumnStretch(0, 1)
        self.environment.set_expanded(False)
        self.environment.show()
        self.export_button.show()
        self.input_note.setText("Assessment complete. Explore another location.")

    def _show_error(self, message: str):
        self._set_busy(False)
        self.error.setText(message)
        self.error.show()
        self.empty_text.setText("We couldn't complete this assessment. Review the message and try again.")
        self.result_status.setText("ANALYSIS UNAVAILABLE")

    def _cancel_if_busy(self):
        if self.client.busy:
            self.client.cancel()

    def _cancelled(self):
        self._set_busy(False)
        self.empty_text.setText("Analysis cancelled. Your selected species and coordinates are ready when you are.")
        self.result_status.setText("AWAITING ANALYSIS")

    def _export_result(self):
        if self.result is None:
            return
        filename = f"wild-locate-{self.result['species'].lower().replace(' ', '-')}.json"
        path, _ = QFileDialog.getSaveFileName(self, "Export habitat assessment", filename, "JSON files (*.json)")
        if not path:
            return
        payload = dict(self.result)
        payload["interpretation"] = self.interpretation.text()
        payload["note"] = "The suitability score is relative and does not represent the probability that the species is currently present."
        file = QSaveFile(path)
        data = (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode("utf-8")
        if not file.open(QIODevice.OpenModeFlag.WriteOnly) or file.write(data) != len(data) or not file.commit():
            self.error.setText("The assessment could not be saved. Choose a writable folder and try again.")
            self.error.show()
            return
        self.input_note.setText("Assessment exported successfully.")

    def closeEvent(self, event):
        self.client.close()
        event.accept()


def create_application(argv=None):
    app = QApplication(sys.argv if argv is None else argv)
    # Qt's headless Windows plugin does not enumerate system fonts. Register
    # installed fonts for test/preview rendering; the native app uses Qt's
    # normal platform font discovery. No system fonts are bundled or copied.
    if app.platformName() == "offscreen" and sys.platform == "win32":
        import os
        font_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for filename in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf", "seguisym.ttf", "georgia.ttf"):
            QFontDatabase.addApplicationFont(str(font_dir / filename))
    app.setApplicationName("Wild-Locate")
    app.setOrganizationName("Wild-Locate")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLESHEET)
    return app


def main():
    app = create_application()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
