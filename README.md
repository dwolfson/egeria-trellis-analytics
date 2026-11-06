# egeria-trellis-analytics (the Analytic Library)

*Moved here from the trellis monorepo (`packages/trellis-analytics`, odpi/egeria-trellis) at commit
`7f4432c60c487679000fa2710f43d37f8eb3de72` (2026-11-02, LS2), with B1's member-scoped table result
(`declaration.py`, `readers/table_rows.py`) from trellis main `778da7616f7604e86a2608725bdcdb5ad971822f` (2026-11-03). The history before that lives in trellis. The distribution
is `egeria-trellis-analytics`; the import package is still `trellis_analytics`, so every entry point, every Dr.Egeria
`implementation` string and every `from trellis_analytics import ...` keeps working.*

```
pip install egeria-trellis-analytics      # then: import trellis_analytics
```

**What it is.** A small Python library of analyses that Resource Explorer (RE) and the Egeria Portal can run.
It holds two kinds of analysis:

- a **routine** reads what is already stored and counts or summarises it (for example `curation_coverage`);
- a **step** is a piece of a survey. It measures one thing per scope (for example one result per table) and
  RE runs it beside its own built-in steps.

Both return their result with an **envelope**: a state word that says how to read the value. There are four,
and no fifth:

| State | Means |
|---|---|
| `measured` | It looked and found a value. |
| `nothing_found` | It looked and there was nothing. This is an answer. |
| `not_established` | It could not look, or could not tell. A reason is required. |
| `not_applicable` | The question does not apply here. A reason is required. |

`nothing_found` and `not_established` are never the same word, so "zero" cannot be shown where the truth is "we
could not look".

For people who use the results, not write them: see the "Analytic Library" section of the RE
[user guide](https://github.com/odpi/egeria-trellis/blob/main/packages/resource-explorer/docs/user-guide.md). Design background:
[`docs/extensibility-walking-skeleton-brief.md`](https://github.com/odpi/egeria-trellis/blob/main/docs/extensibility-walking-skeleton-brief.md) and
[`DESIGN-ANALYTIC-EXTENSIBILITY-WORKING-ASSUMPTIONS.md`](https://github.com/odpi/egeria-trellis/blob/main/packages/resource-explorer/docs/design-notes/DESIGN-ANALYTIC-EXTENSIBILITY-WORKING-ASSUMPTIONS.md).

## What ships

| Module | What it does |
|---|---|
| `trellis_analytics.envelope` | `Envelope` and the four states. |
| `trellis_analytics.manifest` | `RoutineManifest` and `StepManifest`, the declaration of an analysis (subclasses of pyegeria's `AnalyticFunctionSpec`). |
| `trellis_analytics.discovery` | `discover()` finds installed manifests. (`register()` is redundant since pyegeria 6.2.17, which reads the same entry points itself; it warns and adds nothing.) |
| `trellis_analytics.readers` | The reader seam: `OdsRead` (the typed reads a routine or step may ask of RE's registry) and `CatalogueScopeRead` (Curate's node set), and `open_reader(name, ...)`, which finds the installed implementation through the `trellis_analytics.readers` entry-point group. Resource Explorer registers `ods`, `catalogue_scope`, and the two lists discovery checks against (`investigation_purposes`, `question_ids`). With nothing registered (the Portal, without RE) it raises `ReaderMissing` ("no reader installed for ods here"; "no reader for Resource Explorer's catalogue is installed here"), and a routine answers `not_established` with those words. Nothing in the library imports `resource_explorer`. |
| `trellis_analytics.readers.ods`, `.registry_view` | RE's implementations of `OdsRead` and `CatalogueScopeRead`: read-only access to RE's registry (a SQLite file or Postgres). They stay with RE when the library leaves trellis (LS2). |
| `trellis_analytics.routines.curation_coverage` | Published, not yet published and blocked, counted from RE's curation record. |
| `trellis_analytics.routines.context_pack` | Packages what Egeria holds about one database for one kind of consumer, each fact with a state word and provenance. |
| `trellis_analytics.portal` | The Portal tile for `curation_coverage`. |
| `trellis_analytics.step` | `SurveyStep`, the wrapper that runs a user's step code (see below). |
| `trellis_analytics.declaration` | `Declaration`: what an analysis says about its results (kind, measures, absence sentences, extents, confidence, table), and the 0.3 vocabulary (see "The vocabulary" below). |
| `trellis_analytics.declare` | `manifest_properties`: what a step's Egeria declaration says about it, from its manifest. The declaration itself is RE's engine host's (see "Dispatched by Egeria" below). |

## The vocabulary (0.3)

0.3 ships the words of the report-spec micro-flow model (`portal-docs/Internals/report-spec-pipeline-model.md` on
odpi/egeria-workspaces, §2, §5, §7) in `trellis_analytics.declaration`, so manifests, registries and pyegeria bake the
same words. Nothing in the library executes a micro-flow yet; the words come first.

**Structure** (`STRUCTURE_WORDS`): `spec`, `envelope`, `microflow`, `stage`, `producer`, `processor`, `routine`,
`formatter`, `step`.

```
spec       := envelope  microflow  formatters
microflow  := (routine | producer) processor*
routine    := producer+ processor*        # named and reusable; a step is a routine deployed to an engine host
formatter  := shape × renderer
```

| Tuple | Words |
|---|---|
| `STAGE_KINDS` | `producer`, `processor`, `routine` |
| `PRODUCER_KINDS` | `find`, `saved_query`, `count`, `query`, `results`, `literal`, `python`, `typedefs` |
| `PROCESSOR_KINDS` | `derive`, `aggregate`, `join`, `snapshot`, `filter`, `represent` |
| `RESULT_KINDS` | unchanged: `measure`, `series`, `distribution`, `list`, `graph`, `finding`, `proposal`, `table` |
| `SCOPES` | unchanged: the **result level**, `resource`, `container`, `member`, `field` |
| `POPULATIONS` | the population a count reads: `viewer` (every match read and checked: what the caller may see) or `repository` (the repository counts rows, with no per-element visibility check) |

`scope` and `population` are two words (project owner, 2026-11-06). `scope` is the level a result is about.
`population` is whose view a count reads. pyegeria 6.2.22's `count_elements(..., scope=)` keyword is this
`population`.

**Absence.** `ABSENCE_STATES` is `not_measured`, `not_permitted`, `not_applicable`, `nothing_found`.
`nothing_found` is also the envelope's word, so one word means "looked, and there was nothing" at both levels. 0.2
called it `measured_nothing`. A 0.2 `absence` block still loads: the key is read as `nothing_found`, with a
`LegacyWordWarning` (a `DeprecationWarning`). `AbsenceSentences.sentence("measured_nothing")` returns the
`nothing_found` sentence and warns. Nothing the library writes says `measured_nothing`.

**Fields, shapes and value cells (§5).** A `Field` has:

- `name`: an identifier, `[A-Za-z_][A-Za-z0-9_]*`. A dot is always a path, never part of a name.
- `label`: the column name a person reads.
- `kind`: `data`, `cell`, `representation` or `dataset`.
- `type`: `string`, `int`, `float`, `fraction`, `bool`, `datetime`, `guid`, `list<T>`, `map<string,T>`, or
  `representation/<format>`.
- Optionally `unit`, `detail_spec` and `valid_values`. A `dataset` field also has its `shape`, and a `cell` has its
  `companions`.

A `Shape` has `fields`, `extends` (reuse every field of a parent) and `{"include": "Shape.field"}` entries (reuse one
field in its place). A reused field is the declarer's one field, not a copy. `register_shape` refuses a shape that
redeclares a field it reuses.

A cell's companions (`CELL_COMPANIONS`) are:

| Companion | Meaning |
|---|---|
| `state` | One of `CELL_STATES`: `measured` plus the four absences. |
| `completeness` | `complete`, `lower_bound` ("at least N") or `unknown` ("incomplete: some items may be hidden from you"). It replaces 0.2's boolean `capped_field`. |
| `uncertainty` | The spread of the value: `plus_minus`, `low_high` or `band`, declared per measure. |
| `unit`, `as_of`, `basis`, `provenance`, `score` | As in the shipped declaration. |
| `population` | `viewer` or `repository`. |

A cell with no companions list carries `state` only.

**State sets.** A field may narrow its `state` companion to a registered set:
`{"name": "state", "valid_values": "CountStates"}`. A set may only narrow the shared words, never add one, and is
checked at load. Two sets ship:

- `CountStates`: `measured`, `not_measured`, `nothing_found`. A count read under the daemon cannot be `not_permitted`.
- `MemberStates`: `measured`, `not_measured`, `not_permitted`, `nothing_found`. These are B1's per-row states,
  renamed.

`register_state_set` adds others.

**Measures.**

- `completeness_field` names the result field holding the completeness. It may hold a word, or a boolean read as
  `lower_bound` when true (`completeness_of`).
- 0.2's `capped_field` is read as `completeness_field`, with a warning. It is also kept as a read-only property that
  warns.
- `uncertainty: {form, field}` (or `{form: low_high, low_field, high_field}`) declares the spread. It is refused on a
  count (a measure with a `basis`, or a `[]` value) and on a `measured` (exact) read: a count's only uncertainty is its
  completeness. A cell of a measure that declares uncertainty but carries none reads "spread not estimated".

### B1's table, re-expressed on §5

A table result's rows are a `dataset` of a **registered shape**: `table: {shape: "ColumnProfileRow", key_fields: ...}`.
That is the normal case, so Egeria gets one `DataStructure`. Inline `fields` also work. The table-level rules stay on
the table block. `TableDeclaration.as_dataset_field()` gives the table as the dataset field it is. Column by column:

| B1 / shipped 0.2 | §5 / 0.3 | Rule |
|---|---|---|
| `TableColumn.name` | `Field.name` | same; must now be an identifier (B1's `schema`, `table`, `column` all are) |
| (none) | `Field.label` | new, required; the shown column name |
| `type: text / integer / number / boolean / date / datetime` | `string / int / float / bool / datetime / datetime` | rename; accept the old names on read for one minor release with a warning |
| `type: bytes`, `type: duration` | `type: int` or `float` with `unit: "bytes"` / `"seconds"` | §5 carries the unit on the field; `UNIT_COLUMN_TYPES` retires |
| `type: state` + `states: [...]` | **no column**: the row's measured column is `kind: cell` and carries `state` as a companion, narrowed by a named state set | a state is never a column of its own; B1's `states` list becomes the set name (`CountStates`, or a new registered set) |
| `absence: "not counted"` per column | **removed from the field**; the sentence comes from the measure the column is the per-member value of (`AbsenceSentences`, declared once per measure, §5 "absence sentence: not carried in the cell") | so a `cell` column **must** name its measure: `measure_ref` becomes required for `kind: cell`, optional (and ignored) for `data`; a `data` column has no absence (an empty key cell is a refused row, not an absence) |
| `measure_ref` | `measure` | rename; same meaning; still checked against the declaration's measures |
| `key_fields` | unchanged, on the table block | §5 has no key notion; B1 rule 1 stands (member scope ⇒ keys) |
| `max_rows`, `order`, `truncation` | unchanged words; the shown slice is a dataset whose `completeness` is `lower_bound` when truncated | the truncation sentence is the `lower_bound` rendering for a dataset ("the first {shown} of {total}") |
| `summary` | unchanged | the summary measures are the resource-scope `measure` set beside the table |
| `columns: list[TableColumn \| str]` | `shape: "<RegisteredShape>"` **or** inline `fields` | inline keeps the two test declarations valid; a registered shape is the normal case so Egeria gets one `DataStructure` |
| B1's `measured_nothing` in `states` | `nothing_found` | the rename |

**Reading a 0.2 table.** A 0.2 `columns` list is read as `fields`, with one warning, and written as `fields`. The read
follows the table above, with one difference: a 0.2 `type: state` column is kept as a `string` field, so stored rows
keep their keys. Its `valid_values` is the registered set its renamed states equal (B1's list is `MemberStates`), or
the list itself when no set equals it.

A 0.2 per-column `absence` word is dropped on read. A 0.3 table owes its key, truncation, order and summary
(`missing()`), and refuses a cell column that names no measure.

`TableDeclaration.fields()` (the key, then the rest) is now `fields_in_order()`, because `fields` is the inline field
list.

## Writing a routine

A routine is a plain function that takes a reader and what to measure, and returns a result that carries an
`Envelope`. There is no executor: you call it.

```python
from trellis_analytics.readers import ODS, open_reader
from trellis_analytics.routines import curation_coverage

result = curation_coverage(open_reader(ODS, "postgresql://..."), "database", "coco_pharma")
print(result.envelope.result_state.words, "·", result.summary)
print(result.to_dict())
```

To make it available, give it a **manifest** and list the manifest as an entry point. `manifests.py` in this
package does it for its own routines:

```python
from trellis_analytics.manifest import RoutineManifest

CURATION_COVERAGE = RoutineManifest(
    name="curation_coverage",
    function="trellis_analytics.routines.curation_coverage.curation_coverage",
    description="Published, not yet published and blocked, counted from the curation record.",
    returns="CoverageResult (counts with the row ids they count, plus an Envelope)",
    source="ods",              # "ods", "egeria" or "resource": where the data comes from (required)
    version="0.1.0",           # required: a result is stamped with it
    resource_types=["database"],
    family="Curation",
    tags=["curation", "coverage"],
)
```

```toml
# pyproject.toml of the package that ships it
[project.entry-points."pyegeria.analytics"]
curation_coverage = "trellis_analytics.manifests:CURATION_COVERAGE"
```

**Installing the package registers it; report specs name the function by its registered name.** Install the
package and pyegeria (the Portal, Dr.Egeria) and Resource Explorer both find the entry point. There is no
environment variable or list of modules to keep up to date. A report spec says `curation_coverage`, the manifest's
`name`, never the Python path `trellis_analytics.routines.curation_coverage.curation_coverage`. A broken entry point
raises, naming it; it is never skipped silently.

The group is `pyegeria.analytics`. `trellis.analytics`, the group this library used before 2026-10-31, is still read
as an alias while the library is split out of trellis, so a step package built earlier keeps working. Declare
`pyegeria.analytics` in anything new.

Optional manifest fields `purposes` (investigation purposes it serves) and `questions` (question ids such as
`Q-0041`, never wording) are checked at load against Resource Explorer's lists. They are suggestive: an unknown
value is logged as a warning, naming it, and kept.

## Writing a step

A step has three levels:

1. **The code**: `run(inputs) -> list[dict]`. It owns the measurement and the reason.
2. **The wrapper**: `SurveyStep(manifest)`, in this package. It enforces the rules below.
3. **The survey**: an Egeria Survey Definition that names the step.

Each result the code returns is a plain dict. `scope` and `state` are required; a state other than `measured`
or `nothing_found` also needs a `reason`.

```python
def run(inputs):
    rows = inputs.ods.row_count_snapshots(inputs.slug, limit=2)
    if not rows:
        return [{"scope": inputs.slug, "state": "not_established",
                 "reason": "no survey has measured row counts for this database yet"}]
    return [{"scope": "public.orders", "state": "measured",
             "value": {"rowsChanged": 30}, "summary": "+30 rows"}]
```

Its manifest is a `StepManifest`:

```python
MANIFEST = StepManifest(
    name="database_staleness", display_name="Database Staleness",
    function="database_staleness.step.run", description="Rows changed per table since the last survey.",
    returns="one ResourceMeasureAnnotation per table, each with its envelope",
    source="ods", version="0.1.0", resource_types=["database"],
    credential_tier="none",       # "none" or "read_only"; anything higher is refused
    inputs=["ods"],               # what the wrapper hands the code: "resource", "ods", "connection"
    stage="analysis",             # the stage its results belong to
    questions=["Q-0041"], purposes=["Maintain"],
    request_type="re-database-staleness",       # what RE's engine host advertises to Egeria (default re-<name>)
    nothing_to_derive_guard="survey-invalid",   # survey-completed, survey-invalid or survey-failed
)
```

What the wrapper guarantees, so the code does not have to:

- **Only the declared inputs.** An undeclared input is not handed over.
- **No password, ever.** A `connection`, if declared, is opened by the host at the declared tier and passed as
  an object.
- **Read-only at most** on the resource. A higher `credential_tier` is refused when the manifest is built.
- **An envelope on every result.** A result with no state, an unknown state, or no reason where one is required
  is refused, and **nothing from that run is stored**: a partial store would read as the whole answer.

**The reference steps live in trellis until LS2b.** The ten reference steps (database_staleness, hub_tables,
change_rates, statistics_freshness, the six file-system steps and schema_comparison) are in the trellis monorepo,
`packages/trellis-analytics/examples/steps/`, each installable on its own and registered through the same
`pyegeria.analytics` entry point; `database_staleness` is the complete example to copy, and trellis's
[step tutorial](https://github.com/odpi/egeria-trellis/blob/main/packages/trellis-analytics/docs/TUTORIAL-ADD-AN-ANALYTIC-STEP-2026-10-30.md)
walks through it. LS2b ships them as one
distribution, `egeria-trellis-steps`. This repository carries no copy of them: its tests use one fixture step
(`tests/fixtures/ta_fixture_step`), never installed. A step of your own is installed with `pip install -e` (or
`uv pip install -e`), and installing it registers it.

Resource Explorer merges an installed step's manifest into its analysis catalog when it reads it, so a step needs no
commit in RE to show a card. RE's two generators (in trellis, `packages/resource-explorer/scripts/`) write the step's
fallback catalog entry and its Egeria declaration; neither talks to Egeria.

### Dispatched by Egeria

RE's engine host offers each installed step to Egeria as a service of its `SurveyActionEngine`
`ResourceExplorerSurvey`. The step's declaration (generated from its manifest) is one `SurveyActionService`, one
`SupportedGovernanceService` link carrying the manifest's `request_type`, and one `GovernanceActionType`
`ResourceExplorerSurvey::<request type>` with a `GovernanceActionExecutor` to the engine; the manifest's fields ride
in its Additional Properties. The owner runs it with `resource-explorer dr-egeria run engine-host/library/<step>.md`.
When Egeria starts that type on a database, RE claims the engine action, runs the step, publishes its results as
annotations on a SurveyReport and completes the action. If none of the step's results is `measured` or
`nothing_found`, it completes with the manifest's `nothing_to_derive_guard` (no report unless that is
`survey-completed`). A step is not offered if it takes a built-in RE step's name or request type, declares
`connection`, or emits anything but `ResourceMeasureAnnotation`.

### What a step can and cannot reach

A step is in-process, trusted code. RE's host enforces three things:

- **No connection to the resource.** A step that declares `connection` is refused.
- **Reads only through RE's typed methods.** `inputs.ods` offers `row_count_snapshots`, `commit_proofs`,
  `catalogue_scope_events`, `resource_scope_events` and `outbox_status_counts`, each a parameterised SELECT that RE
  owns. A step cannot send SQL: there is no `query`. Each read runs in a separate thread on a connection that cannot
  write (one statement per rolled-back READ ONLY transaction on Postgres; read-only mode, `query_only` and a read-only
  authorizer on SQLite), and the step holds no connection, registry object or database URL. A step that needs a read
  RE does not offer asks for a new typed method; arbitrary SQL from steps would need a read-only database role, a
  follow-up for the owner (ops/DDL).
- **No Egeria identity.** The step's code cannot act in Egeria; the host publishes its results afterwards.

This narrows what a step is handed; it is **not a sandbox**. The thread list, the call stack and the process
environment still reach Resource Explorer's internals, so install only steps you would run as Resource Explorer itself.

## How it is run

The same routine can run in three places. None counts anything of its own; each shows what the routine returned.

| Host | How |
|---|---|
| **Script** | `curation_coverage(open_reader(ODS, url), "database", slug)`, as under "Writing a routine" (Resource Explorer installed, for its readers). |
| **Notebook** | `curation_coverage.ipynb`, shipped in the package (`src/trellis_analytics/examples/`), run with papermill and the parameters `slug` and `ods_url`: `papermill "$(python -c 'from importlib.resources import files; print(files("trellis_analytics") / "examples" / "curation_coverage.ipynb")')" out.ipynb -p slug coco_pharma -p ods_url <url>`. An empty `ods_url` reads `REGISTRY_DATABASE_URL`. |
| **Portal tile** | The registered function `curation_coverage_tile`, shown as **Trellis - Curation Coverage** in the Egeria Portal. Installing this package registers the function and the tile's report spec; there is nothing to set (see "How analytics are found"). `curation_coverage_tile.md`, shipped beside the notebook, is the same spec as a Dr.Egeria report-spec document. |

A **step** is run by RE itself: RE's `survey_step_host` attaches installed steps beside the built-in ones, so the
executor runs them the same way and records their cost. The step's annotations are kept, with their envelope, in
RE's own table. When Egeria dispatches the step to RE's engine host, they are also published as annotations on
the action's SurveyReport.

Resource Explorer's Curate page uses `curation_coverage` directly for its **By analysis** view of a database.

## How analytics are found

**Decision (project owner, 2026-10-31):** "yes to (b)", on Q2 of the Analytic Library split design (2026-10-30, §11):
one way to find analytics, and report specs that name only registered functions.

- **Installing the package registers it.** pyegeria reads the `pyegeria.analytics` entry points of every installed
  package (`trellis.analytics` as an alias during the split). Nothing else to configure.
- **Report specs name the function by its registered name.** `analytic_function: curation_coverage_tile`, not
  `trellis_analytics.portal.curation_coverage_tile`. A report spec is data, and naming only registered functions
  means a report spec cannot make the Portal import arbitrary code. A dotted path still resolves under the allowed
  prefixes (`pyegeria`, `trellis_analytics`), but pyegeria warns with a DeprecationWarning naming the registered
  name, and 6.2.19 refuses it.
- **Report specs register the same way.** **Decision (project owner, 2026-10-31):** "a". A package's report specs
  (its FormatSets) are an entry point too, in the `pyegeria.report_specs` group (`trellis.report_specs` as an
  alias). The value is a callable returning a FormatSetDict. This package declares
  `trellis = "trellis_analytics.portal:report_specs"`, so installing it puts the tile in the Portal's report registry.
- **No `PYEGERIA_REPORT_SPEC_MODULES`.** This package needs pyegeria 6.2.19 or later, which reads the entry points
  and no longer reads that variable (removed in 6.2.19). Do not set it for trellis.

## Install and test

`pip install egeria-trellis-analytics` needs pyegeria 6.2.19 or later and nothing else. It installs no reader of
Resource Explorer's registry: Resource Explorer registers those (`ods`, `catalogue_scope`, and the two lists discovery
checks against) in the `trellis_analytics.readers` entry-point group. Without them, `curation_coverage` and the Portal
tile answer `not_established`, "no reader for Resource Explorer's catalogue is installed here", and discovery skips
its purpose and question checks with a warning. That is the Egeria Portal's case: it installs this package for the
manifests, the envelope words and the tile's report spec.

From a clone:

```
uv sync --extra dev
uv run pytest
```

The tests need no Resource Explorer, no Postgres and no Egeria. `tests/test_reader_seam.py` guards that nothing in
`src/` (or the fixture step) imports `resource_explorer` or a reader implementation. Resource Explorer's own suite (in
trellis) runs the library's routines and the reference steps end to end against its registry.

## Releasing

The version is `__version__` in `src/trellis_analytics/__init__.py`. A maintainer pushes a tag `v<version>` on
odpi/egeria-trellis-analytics; `.github/workflows/release.yml` runs the tests, builds, publishes to PyPI through
trusted publishing (environment `release`) and creates the GitHub release.
