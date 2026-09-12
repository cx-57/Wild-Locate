"""Explicit region selection. Legacy calls continue to mean Massachusetts."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Region:
    code: str
    name: str
    bbox: tuple
    center: tuple
    place_id: int
    examples: tuple = ()


REGIONS = {
    'MA': Region('MA', 'Massachusetts', (-73.60, 41.10, -69.80, 42.95), (42.3718, -72.2820), 2),
    'FL': Region('FL', 'Florida', (-87.70, 24.35, -79.85, 31.10), (28.1, -81.6), 21,
                 ('Nine-banded Armadillo', 'Marsh Rabbit', 'Hispid Cotton Rat')),
    'AZ': Region('AZ', 'Arizona', (-114.90, 31.20, -108.95, 37.10), (32.25, -110.9), 40,
                 ('Collared Peccary', 'Black-tailed Jackrabbit', 'Desert Cottontail')),
}


def get_region(value='MA'):
    if isinstance(value, Region):
        value = value.code
    key = str(value).strip().upper()
    if key not in REGIONS:
        key = next((r.code for r in REGIONS.values() if r.name.casefold() == str(value).casefold()), key)
    if key not in REGIONS:
        raise ValueError('Choose Massachusetts, Florida or Arizona.')
    return REGIONS[key]


def region_root(region='MA'):
    from wildlocate.core.data.environment import get_user_data_dir
    code = get_region(region).code
    root = get_user_data_dir()
    return root if code == 'MA' else root / 'regions' / code
