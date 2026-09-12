import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import rasterio
from rasterio.transform import from_origin

from wildlocate.core.regions import get_region, region_root
from wildlocate.core.registry import (ModelRecord, atomic_json, available_species, list_models,
                                     enable_model, resolve_model, complete)
from wildlocate.core.data.inaturalist import find_place_id
from wildlocate.core.data.regional import validate_location


class RegionTests(unittest.TestCase):
    def test_state_ids_are_exact(self):
        self.assertEqual(find_place_id('Florida'),21)
        self.assertEqual(find_place_id('Arizona'),40)
        self.assertEqual(find_place_id('Massachusetts'),2)

    def test_roots_and_invalid_regions(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'WILDLOCATE_DATA_DIR':folder}):
            self.assertEqual(region_root(),Path(folder).resolve())
            self.assertEqual(region_root('FL'),Path(folder).resolve()/'regions'/'FL')
        with self.assertRaises(ValueError): get_region('../MA')

    def test_boundaries_not_just_bounding_boxes(self):
        validate_location('FL',28.1,-81.6)
        validate_location('AZ',32.25,-110.9)
        for region,lat,lon in [('FL',42.37,-72.28),('AZ',28.1,-81.6),('FL',28.,-86.)]:
            with self.assertRaises(ValueError): validate_location(region,lat,lon)

    def test_models_and_activation_are_isolated(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'WILDLOCATE_DATA_DIR':folder}):
            original=available_species()
            self.assertIn('Bobcat',original)
            self.assertEqual(available_species('FL'),())
            for code,key in [('FL','a'*32),('AZ','b'*32)]:
                root=Path(folder)/'models'/key
                root.mkdir(parents=True)
                (root/'model.joblib').write_bytes(b'test-only')
                (root/'features.csv').write_text('forest\n0.2\n')
                atomic_json(root/'metrics.json',{'species':'Bobcat','predictor_names':['forest'],
                            'selected_model':'test','region':code,'feature_schema':'regional-raster-v1'})
                atomic_json(root/'manifest.json',{'version':1,'species':'Bobcat','region':code})
                enable_model(key)
            self.assertEqual(available_species(),original)
            self.assertFalse(resolve_model('Bobcat').custom)
            self.assertEqual(resolve_model('Bobcat','FL').id,'a'*32)
            self.assertEqual(resolve_model('Bobcat','AZ').id,'b'*32)
            self.assertEqual(list_models('FL')[0].region,'FL')
            # Corrupt region identity must hide the artifact, never cross-load it.
            p=Path(folder)/'models'/('a'*32)/'metrics.json'
            metadata=json.loads(p.read_text());metadata['region']='AZ';atomic_json(p,metadata)
            self.assertEqual(available_species('FL'),())

    def test_original_training_requirements(self):
        from wildlocate.core.training import MIN_OBSERVATIONS
        from wildlocate.core.models.train_species import N_FOLDS
        from wildlocate.core.data.background import generate_background
        import inspect
        self.assertEqual(MIN_OBSERVATIONS,25)
        self.assertEqual(N_FOLDS,5)
        self.assertEqual(inspect.signature(generate_background).parameters['background_ratio'].default,3.)


class RegionalPipelineTests(unittest.TestCase):
    def test_api_region_default_and_validation(self):
        from wildlocate.core.api import PredictionRequest, species
        from pydantic import ValidationError
        request=PredictionRequest(species='Bobcat',latitude=42.,longitude=-72.)
        self.assertEqual(request.region,'MA')
        with self.assertRaises(ValidationError):
            PredictionRequest(region='PR',species='Bobcat',latitude=18.,longitude=-66.)
        self.assertEqual(species('FL')['region'],'FL')

    def test_regional_model_roundtrip(self):
        import contextlib
        import io
        import pandas as pd
        from wildlocate.core.models.train_species import train_species
        from wildlocate.core.predict import predict_species
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'WILDLOCATE_DATA_DIR':folder}):
            root=Path(folder)/'models'/('c'*32)
            root.mkdir(parents=True)
            rng=np.random.default_rng(42)
            feature=rng.random(200)
            frame=pd.DataFrame({'latitude':rng.uniform(26,30,200),
                                'longitude':rng.uniform(-82,-81,200),
                                'forest_fraction_250m':feature,
                                'presence':(feature>.5).astype(int)})
            csv=root/'features.csv';frame.to_csv(csv,index=False)
            with patch('wildlocate.core.models.train_species.build_models',return_value=[{'name':'LogisticRegression','estimator':None}]), contextlib.redirect_stdout(io.StringIO()):
                model_path,metrics_path,metrics=train_species('Test Rabbit',csv,root/'fitted')
            import shutil
            shutil.copyfile(model_path,root/'model.joblib')
            metrics.update(region='FL',feature_schema='regional-raster-v1')
            atomic_json(root/'metrics.json',metrics)
            atomic_json(root/'manifest.json',{'version':1,'species':'Test Rabbit','region':'FL'})
            enable_model('c'*32)
            with patch('wildlocate.core.data.regional.extract_regional_features',return_value={'forest_fraction_250m':.8}) as extract:
                result=predict_species('Test Rabbit',28.,-81.5,'FL')
            extract.assert_called_once_with(28.,-81.5,'FL')
            self.assertEqual(result['region'],'FL')
            self.assertGreater(result['score'],.5)
            self.assertEqual(metrics['number_of_folds'],5)
            with self.assertRaises(FileNotFoundError): resolve_model('Test Rabbit','MA')
            with self.assertRaises(FileNotFoundError): resolve_model('Test Rabbit','AZ')


class RegionalRasterTests(unittest.TestCase):
    @staticmethod
    def _write_raster(path, x, y, value, dtype='float32'):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = np.full((120, 120), value, dtype=dtype)
        transform = from_origin(x - 1800, y + 1800, 30, 30)
        with rasterio.open(
            path, 'w', driver='GTiff', width=data.shape[1], height=data.shape[0],
            count=1, dtype=data.dtype, crs='EPSG:5070', transform=transform,
            nodata=-9999 if np.issubdtype(data.dtype, np.floating) else 255,
        ) as dst:
            dst.write(data, 1)

    @staticmethod
    def _cache_paths(folder, x, y):
        from wildlocate.core.data.regional import TILE_SIZE
        col, row = math.floor(x / TILE_SIZE), math.floor(y / TILE_SIZE)
        root = Path(folder) / 'regions' / 'FL' / 'raster-v1' / f'{col}_{row}'
        return {
            'landcover': root / 'landcover.tif',
            'impervious': root / 'impervious.tif',
            'elevation': root / 'elevation.tif',
        }

    def test_corrupt_cached_raster_is_replaced(self):
        from wildlocate.core.data.regional import tile_paths
        from wildlocate.core.features.extract import project_point
        x, y = project_point(28.1, -81.6)
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'WILDLOCATE_DATA_DIR':folder}):
            paths = self._cache_paths(folder, x, y)
            paths['landcover'].parent.mkdir(parents=True, exist_ok=True)
            paths['landcover'].write_bytes(b'not-a-geotiff')
            self._write_raster(paths['impervious'], x, y, 20, 'uint8')
            self._write_raster(paths['elevation'], x, y, 123.0)

            def fake_download(_service, _coverage, _bbox, _year, output_path):
                self._write_raster(output_path, x, y, 41, 'uint8')

            with patch('wildlocate.core.data.nlcd.download.download_tile', side_effect=fake_download) as download, \
                 patch('wildlocate.core.data.regional.requests.get') as elevation_request:
                returned = tile_paths('FL', x, y)

            download.assert_called_once()
            elevation_request.assert_not_called()
            with rasterio.open(returned['landcover']) as src:
                self.assertEqual(src.crs, rasterio.crs.CRS.from_epsg(5070))
                self.assertEqual(src.count, 1)

    def test_valid_cached_rasters_are_reused_without_network(self):
        from wildlocate.core.data.regional import tile_paths
        from wildlocate.core.features.extract import project_point
        x, y = project_point(28.1, -81.6)
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'WILDLOCATE_DATA_DIR':folder}):
            paths = self._cache_paths(folder, x, y)
            self._write_raster(paths['landcover'], x, y, 41, 'uint8')
            self._write_raster(paths['impervious'], x, y, 20, 'uint8')
            self._write_raster(paths['elevation'], x, y, 123.0)
            with patch('wildlocate.core.data.nlcd.download.download_tile') as download, \
                 patch('wildlocate.core.data.regional.requests.get') as elevation_request:
                returned = tile_paths('FL', x, y)
            self.assertEqual(returned, paths)
            download.assert_not_called()
            elevation_request.assert_not_called()

    def test_extract_regional_features_from_synthetic_rasters(self):
        from wildlocate.core.data.regional import extract_regional_features
        from wildlocate.core.features.extract import project_point
        x, y = project_point(28.1, -81.6)
        expected_keys = [
            'forest_fraction_250m', 'wetland_fraction_250m', 'developed_fraction_250m',
            'open_water_fraction_250m', 'shrubland_fraction_250m', 'grassland_fraction_250m',
            'barren_fraction_250m', 'cropland_fraction_250m', 'mean_impervious_250m',
            'mean_slope_250m', 'forest_fraction_1000m', 'wetland_fraction_1000m',
            'developed_fraction_1000m', 'open_water_fraction_1000m', 'shrubland_fraction_1000m',
            'grassland_fraction_1000m', 'barren_fraction_1000m', 'cropland_fraction_1000m',
            'mean_impervious_1000m', 'mean_slope_1000m', 'terrain_ruggedness_1000m', 'elevation_m',
        ]
        with tempfile.TemporaryDirectory() as folder:
            paths = {
                'landcover': Path(folder) / 'landcover.tif',
                'impervious': Path(folder) / 'impervious.tif',
                'elevation': Path(folder) / 'elevation.tif',
            }
            self._write_raster(paths['landcover'], x, y, 41, 'uint8')
            self._write_raster(paths['impervious'], x, y, 20, 'uint8')
            self._write_raster(paths['elevation'], x, y, 123.0)
            with patch('wildlocate.core.data.regional.tile_paths', return_value=paths):
                features = extract_regional_features(28.1, -81.6, 'FL')

        self.assertEqual(list(features), expected_keys)
        self.assertTrue(all(np.isfinite(value) for value in features.values()))
        self.assertEqual(features['forest_fraction_250m'], 1.0)
        self.assertEqual(features['forest_fraction_1000m'], 1.0)
        self.assertEqual(features['wetland_fraction_250m'], 0.0)
        self.assertEqual(features['mean_impervious_250m'], 20.0)
        self.assertEqual(features['mean_impervious_1000m'], 20.0)
        self.assertEqual(features['elevation_m'], 123.0)
        self.assertAlmostEqual(features['mean_slope_250m'], 0.0)
        self.assertAlmostEqual(features['mean_slope_1000m'], 0.0)
        self.assertAlmostEqual(features['terrain_ruggedness_1000m'], 0.0)


if __name__=='__main__':
    unittest.main()
