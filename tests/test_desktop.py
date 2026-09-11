import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QProcess, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QStyle, QStyleOptionViewItem

from web.app import MainWindow, create_application
from web.client import PredictionClient
from web.formatting import coordinates, feature_display, ordinal


@pytest.fixture(scope="module")
def app():
    app = create_application([])
    yield app


@pytest.fixture
def window(app, monkeypatch):
    window = MainWindow()
    monkeypatch.setattr(window.client.process, "start", Mock(side_effect=AssertionError("Do not launch the prediction worker during UI tests")))
    window.show()
    app.processEvents()
    yield window
    window.close()


def test_opens_without_prediction(window):
    assert window.result is None
    assert window.client.process.state() == QProcess.ProcessState.NotRunning
    assert window.stack.currentWidget() is window.empty_page
    assert window.environment.isHidden()
    assert window.export_button.isHidden()
    assert window.species.completer().model().rowCount() == 5


def test_windowless_launcher_uses_python_with_pipes(app, monkeypatch):
    monkeypatch.setattr("sys.executable", "C:/project/.venv/Scripts/pythonw.exe")
    client = PredictionClient()
    assert client.process.program().replace("\\", "/") == "C:/project/.venv/Scripts/python.exe"
    assert client.process.state() == QProcess.ProcessState.NotRunning


@pytest.mark.parametrize("text", ["", "north", "nan", "inf", "91"])
def test_coordinate_validation_never_starts_worker(window, text):
    window.latitude.setText(text)
    QTest.mouseClick(window.analyze_button, Qt.MouseButton.LeftButton)
    assert not window.error.isHidden()
    assert window.latitude.property("invalid") is True
    assert not window.client.busy


def test_valid_inputs_dispatch_and_busy_state_recovers(window, monkeypatch):
    dispatch = Mock()
    monkeypatch.setattr(window.client, "analyze", dispatch)
    window.analyze()
    dispatch.assert_called_once_with("North American River Otter", 42.3718, -72.2820)
    assert not window.analyze_button.isEnabled()
    assert not window.cancel_button.isHidden()
    window.client.failed.emit("Data is unavailable.")
    assert window.analyze_button.isEnabled()
    assert window.error.text() == "Data is unavailable."
    assert window.cancel_button.isHidden()


def test_cancel_restores_controls_without_losing_inputs(window, monkeypatch):
    def pending_analysis(*args):
        window.client.busy = True
    monkeypatch.setattr(window.client, "analyze", pending_analysis)
    window.analyze()
    window.cancel_button.click()
    assert not window.client.busy
    assert window.analyze_button.isEnabled()
    assert window.latitude.text() == "42.3718"
    assert "cancelled" in window.empty_text.text()


def test_worker_crash_restores_controls(window, monkeypatch):
    def pending_analysis(*args):
        window.client.busy = True
    monkeypatch.setattr(window.client, "analyze", pending_analysis)
    window.analyze()
    window.client.finished(1, QProcess.ExitStatus.CrashExit)
    assert not window.client.busy
    assert window.analyze_button.isEnabled()
    assert "stopped unexpectedly" in window.error.text()


def test_example_coordinates_and_disclosures(window):
    window.species.setText("Red Fox")
    window.example_button.click()
    assert window.latitude.text() == "42.2800"
    assert window.longitude.text() == "-71.3500"
    assert window.result is None
    window.methodology.toggle.click()
    assert not window.methodology.body.isHidden()
    window.methodology.toggle.click()
    assert window.methodology.body.isHidden()


def test_changing_inputs_invalidates_previous_assessment(window):
    # A marker is enough to check invalidation; never show a made-up result.
    window.result = object()
    window.latitude.setText("42.5")
    assert window.result is None
    assert window.stack.currentWidget() is window.empty_page
    assert window.export_button.isHidden()


def test_typed_species_is_normalized_before_dispatch(window, monkeypatch):
    dispatch = Mock()
    monkeypatch.setattr(window.client, "analyze", dispatch)
    window.species.selectAll()
    QTest.keyClicks(window.species, " red fox ")
    window.analyze()
    dispatch.assert_called_once_with("Red Fox", 42.3718, -72.2820)


@pytest.mark.parametrize("species", ["", "   ", "Wolf", "River"])
def test_unsupported_typed_species_never_starts_worker(window, species):
    window.species.setText(species)
    window.analyze()
    assert window.species.property("invalid") is True
    assert "supported species" in window.error.text()
    assert not window.client.busy


def test_species_suggestions_match_within_names(window):
    completer = window.species.completer()
    completer.setCompletionPrefix("otter")
    assert completer.completionCount() == 1
    assert completer.currentCompletion() == "North American River Otter"
    window.result = object()
    window.species.setText("Bobcat")
    assert window.result is None


@pytest.mark.parametrize("width", [780, 1000, 1240])
def test_suggestion_rows_fit_complete_names(window, app, width):
    window.resize(width, 930)
    window.species.clear()
    completer = window.species.completer()
    completer.setCompletionPrefix("")
    completer.complete()
    app.processEvents()
    popup = completer.popup()
    for row in range(popup.model().rowCount()):
        index = popup.model().index(row, 0)
        option = QStyleOptionViewItem()
        option.initFrom(popup)
        popup.itemDelegate().initStyleOption(option, index)
        option.rect = popup.visualRect(index)
        text_rect = popup.style().subElementRect(QStyle.SubElement.SE_ItemViewItemText, option, popup)
        assert text_rect.height() >= option.fontMetrics.height()
        assert text_rect.width() >= option.fontMetrics.horizontalAdvance(index.data())
    popup.hide()


def test_narrow_layout_has_no_horizontal_overflow(window, app):
    window.resize(780, 700)
    app.processEvents()
    assert window.input_card.width() > 500
    assert window.scroll.horizontalScrollBar().maximum() == 0


def test_helper_copy_is_not_clipped(window):
    assert window.empty_text.height() >= window.empty_text.heightForWidth(window.empty_text.width())


@pytest.mark.parametrize("number,expected", [(1, "1st"), (11, "11th"), (22, "22nd"), (23, "23rd"), (70, "70th"), (100, "100th")])
def test_ordinals(number, expected):
    assert ordinal(number) == expected


def test_environment_units_match_extractor_semantics():
    assert feature_display("forest_fraction_1000m", 0.597) == ("Forest cover within 1 km", "59.7%")
    assert feature_display("mean_impervious_250m", 41.235) == ("Impervious surface within 250 m", "41.2%")
    assert feature_display("distance_to_water_m", 336.24) == ("Distance to nearest water", "336 m")
    assert feature_display("mean_slope_1000m", 2.56) == ("Average slope within 1 km", "2.6°")
    assert feature_display("terrain_ruggedness_1000m", 5.2) == ("Terrain ruggedness within 1 km", "5 m")
    assert coordinates(42.28, -71.35) == "42.2800° N  /  71.3500° W"
