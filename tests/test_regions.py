import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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


if __name__=='__main__': unittest.main()


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
        import numpy as np
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
