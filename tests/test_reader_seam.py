"""The reader seam (LS2, brief §2, §1 amended 2026-11-02): the library owns the reads, an installed package answers them.

This repository installs no reader: Resource Explorer registers them (its own tests pin that it does, and that the
Protocols match its implementations). Pins here: with no reader installed the routine and the tile answer
not_established in words instead of importing RE; importing the library resolves no reader; and no module of the library
or of its fixture step imports RE or a reader implementation, at any depth.
"""
import ast
from pathlib import Path

import pytest

from trellis_analytics import readers
from trellis_analytics.envelope import ResultState
from trellis_analytics.readers import ODS, ReaderMissing, open_reader

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "trellis_analytics"

#: Every module of the library.
MOVING = sorted(str(p.relative_to(SRC)) for p in SRC.rglob("*.py"))
CATALOGUE_WORDS = "no reader for Resource Explorer's catalogue is installed here"
#: The implementations that stay behind (RE's), which the moving modules must not import.
STAYS = ("resource_explorer", "trellis_analytics_re", "trellis_analytics.readers.ods", "trellis_analytics.readers.registry_view", "psycopg2")


@pytest.fixture
def no_readers(monkeypatch):
    """This environment as the Portal's: nothing registered in the readers group."""
    real = readers.entry_points
    monkeypatch.setattr(readers, "entry_points",
                        lambda group=None, **kw: [] if group == readers.GROUP else real(group=group, **kw))


def test_a_missing_reader_is_said_in_words(no_readers):
    assert readers.installed_readers() == {}
    with pytest.raises(ReaderMissing) as exc:
        open_reader(ODS, "sqlite:///x")
    assert str(exc.value) == "no reader installed for ods here"


def test_a_reader_that_will_not_load_is_missing_and_says_why(monkeypatch):
    class Broken:
        name, value = ODS, "nowhere.at_all:Reader"

        def load(self):
            raise ImportError("No module named 'nowhere'")
    monkeypatch.setattr(readers, "entry_points", lambda group=None, **kw: [Broken()] if group == readers.GROUP else [])
    with pytest.raises(ReaderMissing, match=r"no reader installed for ods here \(nowhere.at_all:Reader failed to load"):
        open_reader(ODS)


def test_the_routine_with_no_readers_is_not_established_in_the_catalogues_words(no_readers):
    """Condition 2 of the amendment: an absence, never an error, never a zero."""
    from trellis_analytics.routines import curation_coverage

    class Unread:                           # any read at all would be the regression: the catalogue is asked first
        def __getattr__(self, name):
            raise AssertionError(f"read {name} with no catalogue reader installed")
    r = curation_coverage(Unread(), "database", "demo")
    assert r.envelope.result_state is ResultState.NOT_ESTABLISHED
    assert r.envelope.result_state_reason == CATALOGUE_WORDS
    assert r.known == [] and r.groups == [] and r.known_schemas == 0


def test_the_tile_with_no_readers_is_not_established_and_draws_no_counts(no_readers):
    from trellis_analytics.portal import curation_coverage_tile
    tile = curation_coverage_tile("demo", "sqlite:///never-opened")
    assert tile["state"] == ResultState.NOT_ESTABLISHED.value
    assert tile["state_reason"] == CATALOGUE_WORDS and tile["subtitle"] == f"not established · {CATALOGUE_WORDS}"
    assert "Published" not in tile and "Not yet published" not in tile and tile["kpis"] == []


def test_discovery_with_no_readers_skips_its_checks(no_readers):
    from trellis_analytics import discovery
    assert discovery.known_purposes() is None and discovery.known_question_ids() is None


def test_importing_the_library_resolves_no_reader():
    """Condition 4: routines/__init__ stays cheap. Importing every moving module loads no reader implementation and no RE;
    a reader is resolved when a routine runs. (psycopg2 is left out here only because pyegeria's own import loads it; the
    source guard below still refuses it in the library.)"""
    import subprocess
    import sys
    mods = ["trellis_analytics." + p.removesuffix(".py").removesuffix("/__init__").replace("/", ".")
            for p in MOVING if p != "__init__.py"]
    code = ("import sys\n" + "".join(f"import {m}\n" for m in mods) +
            f"print(sorted(m for m in sys.modules if m.startswith({STAYS[:4]!r})))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert out == "[]"


#: A child interpreter in which RE and its reader package cannot be imported at all, as on a Portal without RE.
WITHOUT_RE = """
import importlib.abc, sys
class _Absent(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in ("resource_explorer", "trellis_analytics_re"):
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
sys.meta_path.insert(0, _Absent())
"""


def test_the_routine_and_the_tile_import_and_run_with_re_absent():
    """The Portal imports the routine with no RE installed. Its module level (and the tile's) must name only the seam, so
    the import succeeds; a run then answers not_established instead of raising."""
    import subprocess
    import sys
    code = WITHOUT_RE + (
        "from trellis_analytics.routines import curation_coverage\n"
        "from trellis_analytics.portal import curation_coverage_tile\n"
        "class Unread:\n"
        "    def __getattr__(self, name): raise AssertionError(name)\n"
        "r = curation_coverage(Unread(), 'database', 'demo')\n"
        "t = curation_coverage_tile('demo', 'sqlite:///never-opened')\n"
        "print(r.envelope.result_state.value, t['state'])\n")
    run = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    nes = ResultState.NOT_ESTABLISHED.value
    assert run.stdout.split() == [nes, nes]


def _imports(path: Path):
    """Every module the file imports, at any depth (a lazy import inside a function counts)."""
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_the_guard_sees_the_whole_library():
    assert {"portal.py", "routines/curation_coverage.py", "discovery.py", "readers/__init__.py"} <= set(MOVING)


def _moving_files():
    yield from (SRC / p for p in MOVING)
    yield from sorted((ROOT / "tests" / "fixtures").rglob("*.py"))


@pytest.mark.parametrize("path", list(_moving_files()), ids=lambda p: str(p.relative_to(ROOT)))
def test_what_leaves_with_the_library_imports_no_implementation(path):
    """The seam's guard: a moving module reads through `trellis_analytics.readers`, never RE or a reader it implements,
    not even lazily or behind `except ImportError`."""
    bad = [m for m in _imports(path) if m.startswith(STAYS)]
    assert not bad, f"{path.relative_to(ROOT)} imports {bad}: read through trellis_analytics.readers instead"
