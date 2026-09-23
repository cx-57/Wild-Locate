import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication

from wildlocate.gui.app import MainWindow


class AreaUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['test'])

    def setUp(self):
        self.enterContext(patch('wildlocate.gui.location_map.QWebEngineView', None))
        self.enterContext(patch('wildlocate.gui.app.available_species', return_value=['Bobcat']))
        self.window = MainWindow()
        self.addCleanup(self.window.close)

    def test_mode_radius_preview_and_result_invalidation(self):
        w = self.window
        self.assertTrue(w.radius_controls.isHidden())
        w.analysis_type.setCurrentIndex(1)
        self.assertFalse(w.radius_controls.isHidden())
        self.assertEqual(w.location_map._radius_km, 25)
        w.show_result({'analysis_type': 'regional', 'species': 'Bobcat', 'latitude': 42., 'longitude': -72., 'radius_km': 25, 'grid_spacing_km': 5, 'evaluated_points': 1, 'unavailable_points': 0, 'mean_score': 0.8, 'model': 'Test', 'training_observations': 25, 'points': [{'latitude': 42., 'longitude': -72., 'status': 'ok', 'score': 0.8, 'percentile': 80, 'category': 'Very High'}]})
        self.assertEqual(len(w.location_map._area_points), 1)
        self.assertFalse(w.export_button.isHidden())
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'assessment.json')
            with patch('wildlocate.gui.app.QFileDialog.getSaveFileName', return_value=(path, 'JSON')):
                w.export_result()
            exported = json.loads(Path(path).read_text())
            self.assertEqual(exported['radius_km'], 25)
            self.assertEqual(exported['points'][0]['score'], 0.8)
            self.assertIn('sampled grid', exported['interpretation'])
        w.radius_choice.setCurrentIndex(2)
        self.assertIsNone(w.result)
        self.assertEqual(w.location_map._area_points, [])
        self.assertEqual(w.location_map._radius_km, 50)
        w.analysis_type.setCurrentIndex(0)
        self.assertIsNone(w.location_map._radius_km)

    def test_regional_request_and_cancel_controls(self):
        w = self.window
        w.analysis_type.setCurrentIndex(1)
        # Avoid a real data download while checking the request that the UI sends.
        with patch.object(w.client, 'analyze') as analyze:
            w.analyze()
        self.assertEqual(analyze.call_args.kwargs['radius_km'], 25)
        self.assertFalse(w.analysis_type.isEnabled())
        w.cancelled()
        self.assertTrue(w.analysis_type.isEnabled())

    def test_no_coverage_is_displayed_without_point_metrics(self):
        w = self.window
        w.show_result({'analysis_type': 'regional', 'species': 'Bobcat', 'latitude': 42., 'longitude': -72., 'radius_km': 25, 'grid_spacing_km': 5, 'evaluated_points': 0, 'unavailable_points': 81, 'mean_score': None, 'model': 'Test', 'training_observations': 25, 'points': []})
        self.assertIn('No grid points', w.area_summary.text())
        self.assertTrue(w.environment.isHidden())
        self.assertIs(w.stack.currentWidget(), w.area_page)
