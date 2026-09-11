"""The desktop training workflow, also callable without Qt."""

from datetime import datetime, timezone
import os
import shutil
import uuid

from wildlocate.core.registry import (
    ModelRecord, atomic_json, cleanup_job, complete, custom_root, job_path,
)

MIN_OBSERVATIONS = 25


class TrainingSession:
    def __init__(self, job_id, progress=lambda message: None):
        self.job_id = job_id
        self.workspace = job_path(job_id)
        self.progress = progress
        self.taxon = None
        self.prepared = None

    def initialize_environment(self):
        from wildlocate.cli import cmd_init
        from wildlocate.core.data.environment import get_user_data_dir
        destination = get_user_data_dir() / "raw"
        staging = self.workspace / "environment"
        previous = os.environ.get("WILDLOCATE_DATA_DIR")
        self.progress("Downloading environmental datasets. This may take several minutes…")
        try:
            os.environ["WILDLOCATE_DATA_DIR"] = str(staging)
            cmd_init(None)
        finally:
            if previous is None:
                os.environ.pop("WILDLOCATE_DATA_DIR", None)
            else:
                os.environ["WILDLOCATE_DATA_DIR"] = previous
        # Publish only finished downloads; cancellation leaves installed data intact.
        for source in (staging / "raw").rglob("*"):
            if source.is_file():
                target = destination / source.relative_to(staging / "raw")
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source, target)
        return {}

    def resolve(self, query):
        from wildlocate.core.data.inaturalist import resolve_species
        self.taxon = None
        self.prepared = None
        self.progress("Finding the species on iNaturalist…")
        taxon = resolve_species(query)
        if taxon.get("rank") != "species" or taxon.get("iconic_taxon_name") != "Mammalia":
            raise ValueError("Choose a mammal species. This training workflow supports Massachusetts mammals only.")
        if len(taxon["common_name"]) > 100:
            raise ValueError("This species name is too long to store.")
        self.taxon = taxon
        return taxon

    def prepare(self):
        from wildlocate.core.data.environment import DatasetPaths
        from wildlocate.core.data.inaturalist import (
            clean_species_observations, download_species_observations, save_cleaned_observations,
        )
        self.prepared = None
        if self.taxon is None:
            raise ValueError("Find and confirm a mammal species first.")
        self.progress("Checking the Massachusetts environmental datasets…")
        DatasetPaths().validate()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.progress("Downloading research-grade Massachusetts observations…")
        raw = download_species_observations(
            self.taxon["common_name"], taxon_id=self.taxon["taxon_id"], progress=self.progress,
        )
        cleaned = clean_species_observations(raw)
        if len(cleaned) < MIN_OBSERVATIONS:
            raise ValueError(
                f"Only {len(cleaned):,} usable observations remain out of {len(raw):,}. "
                f"At least {MIN_OBSERVATIONS} are required to attempt spatial validation. "
                "Try another Massachusetts mammal; obscured, duplicate and imprecise locations are excluded."
            )
        save_cleaned_observations(cleaned, self.taxon["common_name"], self.workspace / "samples")
        self.prepared = {"species": self.taxon["common_name"], "raw_count": len(raw), "cleaned_count": len(cleaned)}
        return self.prepared

    def train(self):
        from wildlocate.core.data.background import generate_background
        from wildlocate.core.data.environment import get_user_data_dir
        from wildlocate.core.data.inaturalist import species_slug
        from wildlocate.core.features.build_species_dataset import build_species_dataset
        from wildlocate.core.models.train_species import train_species
        if self.prepared is None or self.taxon is None:
            raise ValueError("Check species data before starting training.")
        name = self.taxon["common_name"]
        samples = self.workspace / "samples"
        pool = self.workspace / "mammal_pool.csv"
        cached_pool = get_user_data_dir() / "training-cache" / "massachusetts_mammal_pool.csv"
        if cached_pool.is_file():
            shutil.copyfile(cached_pool, pool)
        self.progress("Preparing background locations across Massachusetts…")
        generate_background(name, samples_dir=samples, pool_file=pool,
                            taxon_id=self.taxon["taxon_id"], progress=self.progress)
        if pool.is_file():
            cached_pool.parent.mkdir(parents=True, exist_ok=True)
            temporary = cached_pool.with_suffix(f".{self.job_id}.tmp")
            shutil.copyfile(pool, temporary)
            os.replace(temporary, cached_pool)
        self.progress("Extracting environmental features…")
        features = self.workspace / "features.csv"
        build_species_dataset(name, samples / f"{species_slug(name)}_training_points.csv",
                              features, progress=self.progress)
        self.progress("Evaluating candidate models using five spatial folds…")
        model_path, metrics_path, metrics = train_species(
            name, features, self.workspace / "fitted", progress=self.progress,
        )
        self.progress("Checking the completed model and saving it for review…")
        # Validate the serialized artifact and all comparison predictions before publishing.
        import joblib
        import numpy as np
        import pandas as pd
        model = joblib.load(model_path)
        frame = pd.read_csv(features)[metrics["predictor_names"]]
        scores = model.predict_proba(frame)[:, 1]
        if not len(scores) or not np.isfinite(scores).all():
            raise ValueError("The trained model produced invalid comparison scores.")
        review = self.workspace / "review"
        review.mkdir(exist_ok=True)
        shutil.copyfile(model_path, review / "model.joblib")
        shutil.copyfile(metrics_path, review / "metrics.json")
        shutil.copyfile(features, review / "features.csv")
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        atomic_json(review / "manifest.json", {
            "version": 1, "species": name, "taxon": self.taxon,
            "created_at": created_at, "region": "Massachusetts", **self.prepared,
        })
        record = ModelRecord(self.job_id, name, review / "model.joblib", review / "metrics.json", review / "features.csv", True)
        if not complete(record):
            raise ValueError("The model files are incomplete. Training was not published.")
        custom_root().mkdir(parents=True, exist_ok=True)
        # The destination is invisible to discovery until every artifact is ready.
        destination = custom_root() / self.job_id
        if destination.exists():
            raise ValueError("This training session has already saved a model.")
        os.replace(review, destination)
        self.prepared = None
        cleanup_job(self.job_id)
        return {"model_id": self.job_id, "species": name}


def new_job_id():
    return uuid.uuid4().hex
