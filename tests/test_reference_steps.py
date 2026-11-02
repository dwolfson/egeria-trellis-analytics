"""The ten reference steps under examples/steps load against this library alone, with no Resource Explorer.

Each is its own distribution (`trellis-step-<name>`), installed by a host; running one needs a host that hands it an ODS
reader (Resource Explorer's tests run them end to end). Here: each step's manifest builds, names its own step, is a
StepManifest of this library, and its package declares the entry point that registers it and depends on this library.
"""
import importlib
import sys
import tomllib
from pathlib import Path

import pytest

from trellis_analytics.manifest import StepManifest

STEPS = Path(__file__).resolve().parents[1] / "examples" / "steps"
NAMES = sorted(p.name for p in STEPS.iterdir() if (p / "pyproject.toml").exists())


def test_there_are_ten_reference_steps():
    assert len(NAMES) == 10, NAMES


@pytest.mark.parametrize("name", NAMES)
def test_the_step_loads_and_declares_itself(name, monkeypatch):
    project = tomllib.loads((STEPS / name / "pyproject.toml").read_text())["project"]
    assert project["dependencies"] == ["egeria-trellis-analytics>=0.2,<0.3"]
    assert project["entry-points"]["pyegeria.analytics"] == {name: f"{name}.manifest:MANIFEST"}
    monkeypatch.syspath_prepend(str(STEPS / name / "src"))
    for mod in [m for m in sys.modules if m == name or m.startswith(name + ".")]:
        monkeypatch.delitem(sys.modules, mod)
    manifest = importlib.import_module(f"{name}.manifest").MANIFEST
    assert isinstance(manifest, StepManifest) and manifest.name == name
    module, _, func = manifest.function.rpartition(".")
    assert callable(getattr(importlib.import_module(module), func))
