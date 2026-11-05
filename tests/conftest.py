import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def entry_point_dist(tmp_path, monkeypatch):
    """A dist-info built from the package's own pyproject entry-points, so the declared entry point is what's tested."""
    eps = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["entry-points"]["pyegeria.analytics"]
    d = tmp_path / "trellis_analytics_fixture-0.1.0.dist-info"
    d.mkdir()
    (d / "METADATA").write_text("Metadata-Version: 2.1\nName: trellis-analytics-fixture\nVersion: 0.1.0\n")
    (d / "entry_points.txt").write_text(
        "[pyegeria.analytics]\n" + "".join(f"{k} = {v}\n" for k, v in eps.items()))
    monkeypatch.syspath_prepend(str(tmp_path))
    return tmp_path
