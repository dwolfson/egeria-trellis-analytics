"""0.3.1: the 0.2 table API (`TableDeclaration.columns`) still reads, with a DeprecationWarning."""
import warnings

import pytest
from trellis_analytics.declaration import (
    ABSENCE_STATES,
    Declaration,
    LegacyApiWarning,
    LegacyWordWarning,
    TableDeclaration,
)

ABSENCE = {s: f"{s.replace('_', ' ')}: a sentence" for s in ABSENCE_STATES}
TABLE = {
    "key_fields": ["schema", "column"],
    "columns": ["schema", "column",
                {"name": "state", "type": "state", "absence": "not profiled",
                 "states": ["measured", "not_measured", "not_permitted", "measured_nothing"]},
                {"name": "null_count", "type": "integer", "absence": "not counted", "measure_ref": "nulls_total"},
                {"name": "ratio", "type": "number", "unit": "ratio"},
                {"name": "size", "type": "bytes", "unit": "bytes", "absence": "not read"},
                {"name": "took", "type": "duration", "unit": "seconds"},
                {"name": "ok", "type": "boolean"}, {"name": "seen", "type": "datetime"}],
    "order": "schema, column", "truncation": "the first {shown} of {total}", "summary": ["nulls_total"],
}


def load():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", LegacyWordWarning)
        return TableDeclaration.model_validate(TABLE)


def test_columns_has_the_0_2_shape_and_warns():
    t = load()
    with pytest.warns(LegacyApiWarning, match="row_fields"):
        cols = {c.name: c for c in t.columns}
    assert [(c.type) for c in cols.values()] == ["text", "text", "state", "integer", "number", "bytes", "duration",
                                                 "boolean", "datetime"]
    assert cols["size"].unit == "bytes" and cols["took"].unit == "seconds" and cols["ratio"].unit == "ratio"
    assert cols["schema"].key and cols["column"].key and not cols["size"].key
    assert cols["state"].states == ("measured", "not_measured", "not_permitted", "nothing_found")


def test_column_absence_text_survives_a_0_2_load():
    t = load()
    with pytest.warns(LegacyApiWarning):
        cols = {c.name: c for c in t.columns}
    assert cols["null_count"].absence == "not counted" and cols["size"].absence == "not read"
    assert cols["state"].absence == "not profiled" and cols["schema"].absence == ""


def test_a_0_3_table_has_no_column_text_and_the_declaration_helper_fills_cells():
    t = TableDeclaration.model_validate({
        "key_fields": ["a"], "fields": [{"name": "a", "label": "A", "type": "string"},
                                        {"name": "n", "label": "N", "type": "int", "kind": "cell", "measure": "m"}]})
    with pytest.warns(LegacyApiWarning):
        assert [c.absence for c in t.columns] == ["", ""]
    d = Declaration.model_validate({
        "result_kind": "table", "result_kind_note": "rows", "scope": "member", "absence": ABSENCE,
        "measures": [{"name": "m", "unit": "x", "as_of": "surveyed_at", "value_field": "m", "scope": "resource"}],
        "table": t.model_dump()})
    with pytest.warns(LegacyApiWarning):
        cols = d.table_columns()
    assert [c.absence for c in cols] == ["", ABSENCE["not_measured"]]


def test_fields_stays_the_0_3_list():
    assert isinstance(load().fields, list)


def test_the_model_dump_is_unchanged_by_the_kept_text():
    assert "legacy_absence" not in load().model_dump()


def test_a_0_2_manifest_declaration_round_trips_with_its_0_2_absence_word():
    """Shaped like the statistics_freshness example (a 0.2 manifest: `measured_nothing`, no table)."""
    body = {"result_kind": "measure", "scope": "resource",
            "measures": [{"name": "m", "unit": "tables", "as_of": "surveyed_at", "value_field": "m",
                          "scope": "resource"}],
            "absence": {**{k: v for k, v in ABSENCE.items() if k != "nothing_found"}, "measured_nothing": "none"}}
    with pytest.warns(LegacyWordWarning):
        d = Declaration.model_validate(body)
    again = Declaration.model_validate(d.model_dump())   # written with the 0.3 word: no warning needed
    assert again == d and again.absence.nothing_found == "none"
