from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.common.io_utils import read_json
from src.common.errors import TransformError, ConfigError
from .spec import TransformSpec, parse_transform

@dataclass(frozen=True)
class TransformRegistry:
    specs_dir: Path
    transforms: dict[str, TransformSpec]

    @staticmethod
    def load(specs_dir: str | Path) -> "TransformRegistry":
        d = Path(specs_dir)
        if not d.exists() or not d.is_dir():
            raise ConfigError(f"Transform specs dir not found: {d}")
        transforms: dict[str, TransformSpec] = {}
        files = sorted([p for p in d.glob("*.json") if p.is_file() and not p.name.startswith("_")])
        for fp in files:
            data = read_json(fp)
            if not isinstance(data, dict):
                raise TransformError(f"Transform spec must be object: {fp}")
            spec = parse_transform(data)
            if spec.id in transforms:
                raise TransformError(f"Duplicate transform id: {spec.id}")
            transforms[spec.id] = spec
        return TransformRegistry(specs_dir=d, transforms=transforms)

    def get(self, transform_id: str) -> TransformSpec:
        if transform_id not in self.transforms:
            raise TransformError(f"Transform not found: {transform_id}")
        return self.transforms[transform_id]

    def list_ids(self) -> list[str]:
        return sorted(self.transforms.keys())
