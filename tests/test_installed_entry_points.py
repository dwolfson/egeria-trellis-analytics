"""What installing the distribution registers, read from the installed metadata (CI runs this against the built wheel,
not the source tree): the three manifests in pyegeria.analytics and the tile's report specs in pyegeria.report_specs,
each provided by egeria-trellis-analytics, and pyegeria's own registries see them."""
from importlib.metadata import distribution, entry_points

from trellis_analytics import __version__
from trellis_analytics.discovery import discover, origin

DIST = "egeria-trellis-analytics"
MANIFESTS = {"curation_coverage", "context_pack", "curation_coverage_tile"}


def test_the_installed_distribution_is_this_version():
    assert distribution(DIST).version == __version__


def test_every_manifest_is_an_installed_entry_point_of_this_distribution():
    ours = {ep.name for ep in entry_points(group="pyegeria.analytics") if ep.dist and ep.dist.name == DIST}
    assert ours == MANIFESTS
    found = discover(check=False)
    for name in MANIFESTS:
        assert found[name].name == name and origin(name)["package"] == DIST


def test_the_tile_report_spec_is_registered_by_installing():
    ours = [ep for ep in entry_points(group="pyegeria.report_specs") if ep.dist and ep.dist.name == DIST]
    assert [ep.value for ep in ours] == ["trellis_analytics.portal:report_specs"]
    from pyegeria.view.analytic_registry import get_analytic_registry
    from pyegeria.view.base_report_formats import get_report_registry
    assert MANIFESTS <= set(get_analytic_registry())
    assert "Trellis - Curation Coverage" in get_report_registry()
