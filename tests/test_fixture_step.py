"""Discovery and the step wrapper, exercised with one fixture step registered for the test only (tests/fixtures).
The reference steps live in trellis until LS2b; this repository carries no copy of them."""
from pathlib import Path

import pytest

from trellis_analytics.discovery import discover, origin
from trellis_analytics.manifest import StepManifest
from trellis_analytics.step import HostContext, SurveyStep

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixture_step_installed(tmp_path, monkeypatch):
    """A dist-info naming the fixture step in pyegeria.analytics, as installing a step package would write it."""
    d = tmp_path / "ta_fixture_step-0.0.0.dist-info"
    d.mkdir()
    (d / "METADATA").write_text("Metadata-Version: 2.1\nName: ta-fixture-step\nVersion: 0.0.0\n")
    (d / "entry_points.txt").write_text("[pyegeria.analytics]\nta_fixture_step = ta_fixture_step:MANIFEST\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.syspath_prepend(str(FIXTURES))


def test_an_installed_step_is_discovered_with_its_package_named(fixture_step_installed):
    found = discover(check=False)
    assert isinstance(found["ta_fixture_step"], StepManifest)
    assert origin("ta_fixture_step") == {"package": "ta-fixture-step", "entry_point": "ta_fixture_step",
                                         "group": "pyegeria.analytics"}


def test_without_the_fixture_it_is_not_there():
    assert "ta_fixture_step" not in discover(check=False)


def test_the_wrapper_runs_it_and_stores_one_enveloped_result(fixture_step_installed):
    kept = []
    host = HostContext(resource_type="database", slug="demo", producing_run="run-1",
                       store=lambda anns: kept.extend(anns) or len(anns))
    SurveyStep(discover(check=False)["ta_fixture_step"]).run(host)
    assert [(a.scope, a.envelope.result_state.value, a.envelope.producing_run) for a in kept] == \
        [("demo", "measured", "run-1")]
