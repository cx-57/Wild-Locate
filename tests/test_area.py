import json
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from pyproj import Geod
from sklearn.linear_model import LogisticRegression


class AreaTests(unittest.TestCase):
    def area_module(self):
        from wildlocate.core import area
        return area

    def test_grid_stays_within_radius_and_includes_center(self):
        area = self.area_module()
        geod = Geod(ellps="WGS84")
        for lat, lon in [(42.37, -72.28), (0, 179.99), (89.9, 0)]:
            for radius in (10, 25, 50):
                points = area.build_grid(lat, lon, radius)
                self.assertEqual(len(points), 81)
                self.assertTrue(any(abs(p['latitude']-lat) < 1e-8 and abs(p['longitude']-lon) < 1e-8 for p in points))
                for p in points:
                    self.assertLessEqual(geod.inv(lon, lat, p['longitude'], p['latitude'])[2], radius*1000 + 0.001)
                    self.assertTrue(-180 <= p['longitude'] <= 180)

    def test_invalid_radius_and_coordinates_rejected(self):
        area = self.area_module()
        for radius in (0, -10, 11, True, float('nan'), float('inf'), '25'):
            with self.subTest(radius=radius), self.assertRaises(ValueError):
                area.build_grid(42, -72, radius)
        for lat, lon in [(float('nan'), 0), (0, float('inf')), (91, 0), (0, -181), (True, 0)]:
            with self.assertRaises(ValueError):
                area.build_grid(lat, lon, 25)

    def setup_prediction(self, extraction):
        area = self.area_module()
        frame = pd.DataFrame({'habitat': [-1., 0., 1.]})
        model = LogisticRegression().fit(frame, [0, 0, 1])
        from types import SimpleNamespace
        record = SimpleNamespace(species='Bobcat')
        for target, value in [
            ('resolve_model', record),
            ('load_model_and_metadata', (model, {'predictor_names': ['habitat'], 'selected_model': 'LogisticRegression', 'presence_count': 25})),
            ('load_comparison_scores', (np.array([0.1, 0.3, 0.6, 0.9]), frame)),
        ]:
            self.enterContext(patch.object(area, target, return_value=value))
        self.enterContext(patch.object(area, 'extract_features', side_effect=extraction))
        return area

    def test_individual_scores_partial_coverage_and_json(self):
        def extract(lat, lon):
            if lat > 42.5:
                raise ValueError('Requested coordinate cannot be evaluated: missing raster')
            return {'habitat': (lat - 42.37) * 10}
        area = self.setup_prediction(extract)
        result = area.predict_area('Bobcat', 42.37, -72.28, 25)
        good = [p for p in result['points'] if p['status'] == 'ok']
        missing = [p for p in result['points'] if p['status'] == 'unavailable']
        self.assertTrue(good and missing)
        self.assertEqual(result['evaluated_points'], len(good))
        self.assertEqual(result['unavailable_points'], len(missing))
        self.assertGreater(len({p['score'] for p in good}), 1)
        self.assertAlmostEqual(result['mean_score'], sum(p['score'] for p in good)/len(good))
        self.assertNotIn('score', missing[0])
        json.dumps(result, allow_nan=False)

    def test_all_unavailable_is_not_zero_suitability(self):
        area = self.setup_prediction(lambda *_: {'habitat': float('nan')})
        result = area.predict_area('Bobcat', 42.37, -72.28, 25)
        self.assertEqual(result['evaluated_points'], 0)
        self.assertIsNone(result['mean_score'])
        self.assertEqual(result['unavailable_points'], 81)

    def test_missing_dataset_fails_instead_of_hiding_as_coverage(self):
        def missing(*_):
            raise FileNotFoundError('Missing environmental dataset')
        area = self.setup_prediction(missing)
        with self.assertRaises(FileNotFoundError):
            area.predict_area('Bobcat', 42.37, -72.28, 25)

    def test_other_states_use_the_selected_states_extractor(self):
        area = self.setup_prediction(lambda *_: self.fail('MA extractor used for another state'))
        model, metrics = area.load_model_and_metadata(None)
        from wildlocate.core.data.regional import SCHEMA
        for region in ('FL', 'AZ'):
            metadata = dict(metrics, region=region, feature_schema=SCHEMA)
            def extract(lat, lon, selected):
                self.assertEqual(selected, region)
                return {'habitat': lat / 90}
            with patch.object(area, 'load_model_and_metadata', return_value=(model, metadata)), patch('wildlocate.core.data.regional.extract_regional_features', side_effect=extract):
                result = area.predict_area('Bobcat', 28, -81, 10, region)
                self.assertEqual(result['region'], region)
                self.assertEqual(result['evaluated_points'], 81)

    def test_service_rejects_radius_before_prediction(self):
        from wildlocate.core.service import assess_habitat, PredictionError
        with patch('wildlocate.core.service.available_species', return_value=['Bobcat']):
            with self.assertRaises(PredictionError) as error:
                assess_habitat('Bobcat', 42, -72, radius_km=100)
            self.assertEqual(error.exception.code, 'invalid_radius')

    def test_existing_point_request_still_uses_point_prediction(self):
        from wildlocate.core.service import assess_habitat
        with patch('wildlocate.core.service.available_species', return_value=['Bobcat']), patch('wildlocate.core.service.predict_species', return_value={'features': {}, 'score': 0.5}):
            self.assertEqual(assess_habitat('bobcat', 42, -72)['score'], 0.5)


if __name__ == '__main__':
    unittest.main()
