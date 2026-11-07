"""0.3's shared vocabulary (BRIEF RS-W1-1 §2; report-spec-pipeline-model §2, §5, §7): the micro-flow words, the one
absence word `nothing_found` (0.2's `measured_nothing` read, never written), `completeness` replacing `capped_field`,
`uncertainty` per measure, named state sets, §5 fields and shapes, and B1's table as a dataset of a registered shape."""
import re
import warnings

import pytest
from pydantic import ValidationError
from trellis_analytics.declaration import (
    ABSENCE_STATES,
    CELL_COMPANIONS,
    COMPLETENESS,
    POPULATIONS,
    PROCESSOR_KINDS,
    PRODUCER_KINDS,
    SCOPES,
    SHAPES,
    STAGE_KINDS,
    STATE_SETS,
    AbsenceSentences,
    CountStates,
    Declaration,
    Field,
    LegacyWordWarning,
    MeasureDeclaration,
    Shape,
    TableDeclaration,
    completeness_of,
    refusal,
    register_shape,
    register_state_set,
    resolve_fields,
)

SENTENCES = {"not_measured": "not measured yet", "not_permitted": "not permitted", "not_applicable": "does not apply",
             "nothing_found": "looked, and there were none"}
LEGACY = {**{k: v for k, v in SENTENCES.items() if k != "nothing_found"}, "measured_nothing": SENTENCES["nothing_found"]}
MEASURE = {"name": "n", "unit": "tables", "as_of": "asOf", "value_field": "count"}


@pytest.fixture(autouse=True)
def _registries():
    """Shapes and state sets are process-wide registries: each test leaves them as it found them."""
    shapes, sets = dict(SHAPES), dict(STATE_SETS)
    yield
    SHAPES.clear(), SHAPES.update(shapes)
    STATE_SETS.clear(), STATE_SETS.update(sets)


def refused(model, body) -> str:
    with pytest.raises(ValidationError) as exc:
        model.model_validate(body)
    return refusal(exc.value)


# ── the words ───────────────────────────────────────────────────────────────────────────────────────────────────

def test_the_micro_flow_and_cell_words_are_the_notes():
    assert STAGE_KINDS == ("producer", "processor", "routine")
    assert PRODUCER_KINDS == ("find", "saved_query", "count", "query", "results", "literal", "python", "typedefs")
    assert PROCESSOR_KINDS == ("derive", "aggregate", "join", "snapshot", "filter", "represent")
    assert ABSENCE_STATES == ("not_measured", "not_permitted", "not_applicable", "nothing_found")
    assert COMPLETENESS == ("complete", "lower_bound", "unknown")
    assert CountStates == ("measured", "not_measured", "nothing_found")
    assert "population" in CELL_COMPANIONS and "scope" not in CELL_COMPANIONS


def test_population_and_scope_are_two_words():
    """Owner, 2026-11-06: the population a count reads is `population`; `scope` keeps the result level."""
    assert POPULATIONS == ("viewer", "repository")
    assert SCOPES == ("resource", "container", "member", "field")


# ── nothing_found, the one absence word ─────────────────────────────────────────────────────────────────────────

def test_a_02_absence_block_loads_with_a_warning_and_is_written_with_the_03_word():
    with pytest.warns(LegacyWordWarning, match="'measured_nothing' is a 0.2 word, read as 'nothing_found'"):
        a = AbsenceSentences.model_validate(LEGACY)
    assert a.nothing_found == SENTENCES["nothing_found"]
    dumped = a.model_dump()
    assert "measured_nothing" not in dumped and dumped == SENTENCES


def test_the_02_word_asked_of_sentence_gives_the_nothing_found_sentence_and_warns():
    a = AbsenceSentences.model_validate(SENTENCES)
    with pytest.warns(LegacyWordWarning):
        assert a.sentence("measured_nothing") == SENTENCES["nothing_found"]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert a.sentence("nothing_found") == SENTENCES["nothing_found"]


def test_both_words_with_different_sentences_are_refused():
    said = refused(AbsenceSentences, {**SENTENCES, "measured_nothing": "something else"})
    assert "declare nothing_found only" in said


def test_a_02_declaration_warns_once_per_legacy_block():
    body = {"result_kind": "measure", "absence": LEGACY,
            "measures": [{**MEASURE, "capped_field": "paging.capped"}]}
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        d = Declaration.model_validate(body)
    words = sorted(re.search(r"'(\w+)' is a 0.2 word", str(w.message)).group(1) for w in seen
                   if issubclass(w.category, LegacyWordWarning))
    assert words == ["capped_field", "measured_nothing"]
    dumped = d.model_dump()
    assert "measured_nothing" not in dumped["absence"] and "capped_field" not in dumped["measures"][0]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert Declaration.model_validate(dumped) == d   # what 0.3 writes, 0.3 reads with no warning


# ── completeness and uncertainty ────────────────────────────────────────────────────────────────────────────────

def test_completeness_reads_a_word_or_02s_boolean_and_never_assumes_complete():
    assert completeness_of(True) == "lower_bound" and completeness_of(False) == "complete"
    assert completeness_of("lower_bound") == "lower_bound" and completeness_of(None) == "unknown"
    m = MeasureDeclaration.model_validate({**MEASURE, "completeness_field": "paging.complete"})
    assert m.completeness_field == "paging.complete"


def test_capped_field_and_completeness_field_both_declared_differently_are_refused():
    said = refused(MeasureDeclaration, {**MEASURE, "capped_field": "a", "completeness_field": "b"})
    assert "declare completeness_field only" in said


def test_uncertainty_is_declared_per_measure_with_its_form():
    m = MeasureDeclaration.model_validate({**MEASURE, "unit": "rows", "value_field": "estimate",
                                           "uncertainty": {"form": "plus_minus", "field": "error"}})
    assert m.uncertainty.form == "plus_minus"
    m = MeasureDeclaration.model_validate({**MEASURE, "uncertainty": {"form": "low_high", "low_field": "lo",
                                                                       "high_field": "hi"}})
    assert (m.uncertainty.low_field, m.uncertainty.high_field) == ("lo", "hi")
    assert "is not one of the forms" in refused(MeasureDeclaration, {**MEASURE, "uncertainty": {"form": "sigma"}})
    assert "names low_field and high_field" in refused(
        MeasureDeclaration, {**MEASURE, "uncertainty": {"form": "low_high", "field": "x"}})


@pytest.mark.parametrize("over", [
    {"basis": {"denominator_field": "total", "denominator_label": "tables"}},
    {"value_field": "tables[]"},
])
def test_uncertainty_on_a_count_is_refused(over):
    said = refused(MeasureDeclaration, {**MEASURE, **over, "uncertainty": {"form": "plus_minus", "field": "e"}})
    assert "declares uncertainty on a count" in said


def test_uncertainty_on_an_exact_read_is_refused_and_on_an_estimate_is_accepted():
    measure = {**MEASURE, "uncertainty": {"form": "band", "field": "band"}}
    body = {"result_kind": "measure", "absence": SENTENCES, "measures": [measure]}
    assert "an exact read has no spread" in refused(Declaration, {**body, "confidence": {"form": "measured"}})
    d = Declaration.model_validate({**body, "confidence": {"form": "estimated", "method": "a 1% sample"}})
    assert d.measures[0].uncertainty.form == "band"


# ── state sets ──────────────────────────────────────────────────────────────────────────────────────────────────

def cell(**over):
    return {"name": "term_count", "label": "Terms", "kind": "cell", "type": "int", **over}


def test_a_cell_names_a_registered_state_set_and_its_cells_hold_only_those_states():
    f = Field.model_validate(cell(companions=[{"name": "state", "valid_values": "CountStates"}, "completeness",
                                               "as_of"]))
    assert f.companion_names() == ["state", "completeness", "as_of"] and f.states() == CountStates


def test_a_state_set_that_is_not_registered_or_not_a_subset_is_refused_at_load():
    assert "state set 'Nope', which is not registered" in refused(
        Field, cell(companions=[{"name": "state", "valid_values": "Nope"}]))
    assert "is not a subset of its words" in refused(
        Field, cell(companions=[{"name": "state", "valid_values": ["measured", "unknowable"]}]))
    with pytest.raises(ValidationError) as exc:
        register_state_set("MaybeStates", ("measured", "maybe"))
    assert "never adds one" in refusal(exc.value)


def test_a_cell_with_no_companions_carries_state_only():
    assert Field.model_validate(cell()).companion_names() == ["state"]


def test_companions_belong_to_a_cell_and_name_known_companions():
    assert "companions belong to a cell" in refused(Field, cell(kind="data", companions=["state"]))
    assert "is not a cell companion" in refused(Field, cell(companions=["colour"]))
    assert Field.model_validate(cell(companions=[{"name": "population", "valid_values": ["viewer"]}]))


# ── fields ──────────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name, said", [
    ("terms.count", "a dot is a path, never part of a name"),
    ("1st", "is not an identifier"),
    ("display name", "is not an identifier"),
])
def test_a_field_name_is_an_identifier(name, said):
    assert said in refused(Field, {"name": name, "label": "X", "type": "string"})


@pytest.mark.parametrize("ftype", ["string", "int", "float", "fraction", "bool", "datetime", "guid", "list<string>",
                                   "map<string,int>", "map<string, float>"])
def test_the_field_types_are_the_notes(ftype):
    assert Field.model_validate({"name": "x", "label": "X", "type": ftype}).type == ftype


def test_a_field_refuses_an_unknown_type_and_a_missing_label():
    assert "is not a field type" in refused(Field, {"name": "x", "label": "X", "type": "integer"})
    assert "declares no label" in refused(Field, {"name": "x", "type": "string"})


def test_a_representation_field_in_the_notes_short_form():
    f = Field.model_validate({"name": "mermaidGraph", "kind": "representation", "format": "mermaid"})
    assert f.type == "representation/mermaid" and f.label == "mermaidGraph"
    assert "a representation field, and only one" in refused(
        Field, {"name": "g", "label": "G", "type": "representation/mermaid"})


def test_a_dataset_field_names_a_shape_and_only_a_dataset_does():
    assert "names no shape" in refused(Field, {"name": "rows", "label": "Rows", "kind": "dataset"})
    assert "a shape belongs to a dataset" in refused(Field, {"name": "x", "label": "X", "type": "string",
                                                             "shape": "S"})


# ── shapes: fields shared, not copied ───────────────────────────────────────────────────────────────────────────

COMMON = {"fields": [{"name": "display_name", "label": "Display Name", "type": "string"},
                     {"name": "description", "label": "Description", "type": "string"}]}


def test_two_shapes_extending_one_share_its_field():
    register_shape("CommonRow", COMMON)
    register_shape("GlossaryRow", {"extends": "CommonRow",
                                   "fields": [{"name": "language", "label": "Language", "type": "string"}]})
    register_shape("TermRow", {"extends": "CommonRow",
                               "fields": [{"name": "summary", "label": "Summary", "type": "string"}]})
    glossary, term = resolve_fields("GlossaryRow"), resolve_fields("TermRow")
    assert [f.name for _, f in glossary] == ["display_name", "description", "language"]
    [g] = [(d, f) for d, f in glossary if f.name == "display_name"]
    [t] = [(d, f) for d, f in term if f.name == "display_name"]
    assert g[0] == t[0] == "CommonRow" and g[1] is t[1]   # one display_name, declared by CommonRow


def test_a_shape_that_redeclares_a_field_it_extends_is_refused():
    register_shape("CommonRow", COMMON)
    with pytest.raises(ValueError, match="a reused field is shared, never redeclared"):
        register_shape("BadRow", {"extends": "CommonRow",
                                  "fields": [{"name": "display_name", "label": "Name", "type": "string"}]})
    assert "BadRow" not in SHAPES


def test_an_include_reuses_one_field_in_its_place():
    register_shape("CommonRow", COMMON)
    register_shape("NoteRow", {"fields": [{"name": "title", "label": "Title", "type": "string"},
                                          {"include": "CommonRow.description"}]})
    assert [(d, f.name) for d, f in resolve_fields("NoteRow")] == [("NoteRow", "title"), ("CommonRow", "description")]
    with pytest.raises(ValueError, match="has no field 'colour'"):
        register_shape("X", {"fields": [{"include": "CommonRow.colour"}]})
    with pytest.raises(ValueError, match="extends 'Nowhere', which is not registered"):
        register_shape("Y", {"extends": "Nowhere"})


# ── B1's table as a dataset of a registered shape ───────────────────────────────────────────────────────────────

PROFILE_ROW = {"fields": [
    {"name": "schema", "label": "Schema", "type": "string"},
    {"name": "table", "label": "Table", "type": "string"},
    {"name": "column", "label": "Column", "type": "string"},
    {"name": "declared_type", "label": "Declared Type", "type": "string"},
    {"name": "null_count", "label": "Nulls", "kind": "cell", "type": "int", "measure": "nulls_total",
     "companions": [{"name": "state", "valid_values": "MemberStates"}, "completeness"]},
]}


def member_table(table):
    return {"result_kind": "table", "result_kind_note": "one row per column", "scope": "member",
            "measures": [{**MEASURE, "name": n, "unit": "columns", "value_field": n} for n in
                         ("columns_total", "nulls_total")],
            "absence": SENTENCES, "confidence": {"form": "measured"}, "answers": [], "table": table}


TABLE = {"shape": "ColumnProfileRow", "key_fields": ["schema", "table", "column"],
         "order": "schema, table, column as the catalog lists them",
         "truncation": "the first {shown} of {total} columns", "summary": ["columns_total", "nulls_total"]}


def test_a_b1_table_is_a_dataset_of_a_registered_shape_and_round_trips():
    register_shape("ColumnProfileRow", PROFILE_ROW)
    with warnings.catch_warnings():
        warnings.simplefilter("error")   # 0.3 words only: no legacy warning
        d = Declaration.model_validate(member_table(TABLE))
        assert d.is_table_result() and d.missing() == []
        assert d.extents[0].fields == ["schema", "table", "column", "declared_type", "null_count"]
        assert d.table.column("null_count").states() == ("measured", "not_measured", "not_permitted", "nothing_found")
        dataset = d.table.as_dataset_field()
        assert (dataset.kind, dataset.shape) == ("dataset", "ColumnProfileRow")
        assert Field.model_validate(dataset.model_dump()) == dataset
        assert Declaration.model_validate(d.model_dump()) == d
    assert d.table.truncation_words(1000, 1236) == "the first 1000 of 1236 columns"
    assert d.table.truncation_words(5, 5) == ""


def test_a_table_names_a_registered_shape_or_inline_fields_never_both():
    assert "shape 'Nope', which is not registered" in refused(TableDeclaration, {"shape": "Nope"})
    register_shape("ColumnProfileRow", PROFILE_ROW)
    assert "its fields are said in one place" in refused(
        TableDeclaration, {"shape": "ColumnProfileRow", "fields": PROFILE_ROW["fields"]})


def test_a_tables_cell_column_must_name_its_measure():
    fields = [{"name": "k", "label": "K", "type": "string"},
              {"name": "v", "label": "V", "kind": "cell", "type": "int"}]
    assert "cell column v names no measure" in refused(TableDeclaration, {"fields": fields, "key_fields": ["k"]})


def test_a_02_table_is_read_as_fields_with_the_reconciled_words():
    with pytest.warns(LegacyWordWarning, match="'columns' is a 0.2 word, read as 'fields'"):
        t = TableDeclaration.model_validate({"key_fields": ["k"], "columns": [
            "k",
            {"name": "state", "type": "state", "absence": "x",
             "states": ["measured", "not_measured", "not_permitted", "measured_nothing"]},
            {"name": "other_state", "type": "state", "states": ["measured", "not_applicable"]},
            {"name": "size", "type": "bytes", "unit": "bytes", "absence": "not read"},
            {"name": "took", "type": "duration", "unit": "seconds"},
            {"name": "nulls", "type": "integer", "absence": "not counted", "measure_ref": "nulls_total"}]})
    got = {f.name: f for f in t.fields}
    assert got["k"].label == "K" and got["k"].type == "string"
    assert got["state"].valid_values == "MemberStates"           # B1's states list, renamed, is a registered set
    assert got["other_state"].valid_values == ["measured", "not_applicable"]   # no set equals it: kept as listed
    assert (got["size"].type, got["size"].unit) == ("int", "bytes")
    assert (got["took"].type, got["took"].unit) == ("float", "seconds")
    assert (got["nulls"].kind, got["nulls"].measure) == ("cell", "nulls_total")
    dumped = t.model_dump()
    assert "columns" not in dumped and "absence" not in dumped["fields"][1]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert TableDeclaration.model_validate(dumped) == t


def test_a_shape_model_validates_include_entries_in_place():
    s = Shape.model_validate({"fields": [{"include": "CommonRow.description"}]})
    assert s.declared() == [] and s.fields[0].include == "CommonRow.description"
    assert "is not '<Shape>.<field>'" in refused(Shape, {"fields": [{"include": "description"}]})
