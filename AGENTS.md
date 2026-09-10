Wild-Locate UI Handoff

The habitat-suitability backend is already working. Please build the user-facing interface around it without changing the existing ML/data pipeline unless something is strictly necessary for integration.

CORE BACKEND FLOW

Current working command:

python3 src/predict.py --species "North American River Otter" --lat 42.3718 --lon -72.2820

The backend already:
1. Accepts a species name
2. Accepts latitude and longitude
3. Extracts environmental features
4. Loads the trained species-specific ML model
5. Returns:
   - relative habitat suitability score
   - suitability percentile
   - category
   - model type
   - number of species observations used for training
   - environmental feature values

Important:
- The score is RELATIVE HABITAT SUITABILITY.
- Do NOT label it as probability that the animal is present.
- Do NOT modify model training, environmental extraction, background generation, or datasets.

Existing trained species currently include:
- Bobcat
- Fisher
- North American River Otter
- Red Fox
- Coyote

--------------------------------------------------
PHASE 1 — MAKE PREDICTION OUTPUT PROGRAMMATIC
--------------------------------------------------

Refactor only enough so that the prediction logic can be called from Python instead of only through terminal output.

Ideally expose something like:

predict_species(species, latitude, longitude)

and return a dictionary like:

{
    "species": "North American River Otter",
    "latitude": 42.3718,
    "longitude": -72.2820,
    "score": 0.420,
    "percentile": 70,
    "category": "High",
    "model": "Random Forest",
    "training_observations": 534,
    "features": {
        "forest_fraction_250m": 0.0,
        "forest_fraction_1000m": 0.2798,
        ...
    }
}

IMPORTANT:
The existing CLI in src/predict.py must continue to work.

Do not duplicate prediction logic. The CLI and web API should both call the same prediction function.

--------------------------------------------------
PHASE 2 — ADD A THIN API
--------------------------------------------------

Create a small Python API around the prediction function.

FastAPI is preferred.

Suggested structure:

src/
    api.py

Endpoint:

POST /predict

Request:

{
    "species": "Red Fox",
    "latitude": 42.28,
    "longitude": -71.35
}

Response:

{
    "species": "Red Fox",
    "latitude": 42.28,
    "longitude": -71.35,
    "score": 0.529,
    "percentile": 62,
    "category": "High",
    "model": "LogisticRegression",
    "training_observations": 1505,
    "features": {...}
}

Handle errors cleanly:
- unsupported/untrained species
- latitude outside -90 to 90
- longitude outside -180 to 180
- coordinate outside available environmental rasters
- model/extraction errors

Return readable error messages rather than stack traces to the frontend.

--------------------------------------------------
PHASE 3 — BUILD THE FRONTEND
--------------------------------------------------

Put frontend code inside:

web/

Use React/Vite unless there is a strong reason to use something else.

Main page should be clean and visually polished.

User inputs:

1. Species selector
   - Bobcat
   - Fisher
   - North American River Otter
   - Red Fox
   - Coyote

2. Location input
   - Latitude
   - Longitude

3. "Analyze Habitat" button

The page should initially explain Wild-Locate in one short sentence:

"Wild-Locate uses species observations and environmental data to estimate how suitable a location is as habitat for wildlife."

--------------------------------------------------
PHASE 4 — RESULTS UI
--------------------------------------------------

After prediction, prominently display:

Species
Location
Suitability category
Suitability percentile
Relative habitat suitability score

The percentile/category should be the main visual result.

Categories:

0–19       Very Low
20–39      Low
40–59      Moderate
60–79      High
80–100     Very High

Example:

North American River Otter

HIGH HABITAT SUITABILITY

70th percentile

Relative suitability score: 0.420

"This location received a higher habitat-suitability score than approximately 70% of comparison locations for this species."

Also display:

Model: Random Forest
Training observations: 534

Do not show language implying:
"70% chance an otter lives here"

Instead include:

"The suitability score is relative and does not represent the probability that the species is currently present."

--------------------------------------------------
PHASE 5 — ENVIRONMENTAL BREAKDOWN
--------------------------------------------------

Do not dump raw variable names like:

forest_fraction_1000m

directly on the main screen.

Translate them into readable labels.

Examples:

Forest cover within 250 m
Forest cover within 1 km
Wetland cover within 250 m
Wetland cover within 1 km
Developed land within 250 m
Developed land within 1 km
Open water within 250 m
Open water within 1 km
Impervious surface within 250 m
Impervious surface within 1 km
Elevation
Average slope within 250 m
Average slope within 1 km
Terrain ruggedness
Distance to nearest water
Distance to nearest road

Format values nicely:

forest_fraction → percentage
0.597 → 59.7%

distance → meters
336.24 → 336 m

elevation → meters
159.25 → 159 m

Do not show 15 decimal places.

Put these in an expandable section such as:

"Environmental Conditions"

rather than making them dominate the page.

--------------------------------------------------
PHASE 6 — VISUAL DESIGN
--------------------------------------------------

The interface should feel like a conservation/wildlife technology product rather than a school assignment.

Suggested layout:

NAVBAR
Wild-Locate logo/name

HERO
"Find where wildlife can thrive."

Short explanation

INPUT CARD
Species
Latitude
Longitude
Analyze Habitat

RESULT CARD
Species
Category
Percentile
Suitability gauge/progress visualization
Short interpretation

ENVIRONMENT CARD
Readable environmental variables

METHODOLOGY / INFO
Short explanation of:
- iNaturalist species observations
- NLCD land cover
- USGS elevation
- Massachusetts hydrography
- Massachusetts roads
- machine-learning habitat model

Do not make scientific claims beyond what the backend supports.

--------------------------------------------------
PHASE 7 — LOCATION UX
--------------------------------------------------

For the first version, manual latitude/longitude input is sufficient.

If time permits, improve it by allowing the user to click a location on a Massachusetts map and automatically fill latitude/longitude.

The map should be secondary to the core prediction system.

Do NOT attempt statewide habitat maps or wildlife corridors yet.

--------------------------------------------------
PHASE 8 — TESTING
--------------------------------------------------

Confirm the web result matches the terminal result exactly.

Regression test:

Species:
North American River Otter

Coordinates:
42.3718
-72.2820

Expected:

score ≈ 0.420
percentile = 70
category = High
model = Random Forest
training observations = 534

Also test:

Red Fox
42.28
-71.35

Previously returned approximately:

score = 0.529
percentile = 62
category = High

The frontend result must use the same backend calculation and not recreate any model logic in JavaScript.

--------------------------------------------------
IMPORTANT RULES
--------------------------------------------------

1. Do not retrain the models.
2. Do not modify feature definitions.
3. Do not change presence/background generation.
4. Do not replace the ML system.
5. Do not create fake/demo prediction values.
6. All displayed predictions must come from the existing Python backend.
7. Preserve the existing terminal prediction functionality.
8. Keep frontend and backend code cleanly separated.
9. Make small commits as each phase works.
10. Prioritize a reliable demo over adding unnecessary features.