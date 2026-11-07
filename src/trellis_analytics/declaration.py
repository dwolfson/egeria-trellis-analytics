"""The declaration: what an analysis says about its own results, so a screen, a chat answer and an Egeria publish can
use them with no code written for that analysis (design note DESIGN-DECLARED-EXTENSIBILITY-RENDERING-CHAT-CONFIDENCE,
§1 "what a declaration carries", §2 result kinds, §4 confidence forms).

One model, two carriers. A library step carries it as `StepManifest.declaration`; Resource Explorer's own analyses
carry the same fields under `declaration:` in `analysis_catalog.yaml`, validated by this same class
(`analysis_catalog_reader`). The generator copies a step's declaration into its catalogue entry unchanged.

Two levels (owner's answer 2, §1): the **minimum** an experiment runs with is `result_kind`, `measures` and
`absence`, and this class refuses anything less. A repeatable analysis is promoted to a **full** declaration by adding
`extents`, `confidence`, `answers` and `scope`; `missing()` names what a minimum declaration still lacks.

Every refusal is a sentence naming the field and the value refused, as the manifest's own validators word theirs.

0.3 (BRIEF RS-W1-1; report-spec-pipeline-model §2, §5, §7) adds the shared vocabulary: the micro-flow words
(`STAGE_KINDS`, `PRODUCER_KINDS`, `PROCESSOR_KINDS`), §5's `Field` and `Shape` with their registry, value-cell
companions, named state sets, `completeness` (replacing `capped_field`), `uncertainty` per measure, `POPULATIONS`, and
`nothing_found` as the one absence word. A table's rows are a dataset of a registered shape (or inline fields). A 0.2
declaration still loads: each 0.2 word is read as its 0.3 word with a `LegacyWordWarning` and never written.
"""
from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic import Field as _Default  # `Field` is §5's field model below

#: §2: the fixed vocabulary. A ninth kind is a design change, not a value a declaration may invent.
RESULT_KINDS = ("measure", "series", "distribution", "list", "graph", "finding", "proposal", "table")

#: §1's four absences, each a sentence the analysis declares, never one a renderer improvises. How they meet the
#: envelope's states (`envelope.ResultState`): `nothing_found` is `nothing_found` (one word at both levels since 0.3);
#: `not_measured` and `not_permitted` are both `not_established`, told apart by the reason (could not look, versus not
#: allowed to); `not_applicable` is `not_applicable`.
ABSENCE_STATES = ("not_measured", "not_permitted", "not_applicable", "nothing_found")

#: The absence words of earlier releases, accepted on read and never written: old word -> the word it is now. 0.2
#: called "looked, and there was nothing" `measured_nothing`; 0.3 uses the envelope's word, `nothing_found`.
LEGACY_ABSENCE_WORDS = {"measured_nothing": "nothing_found"}

#: The state a value cell carries when there is a value: the absences plus this one (§5 `state`).
CELL_STATES = ("measured",) + ABSENCE_STATES


class LegacyWordWarning(DeprecationWarning):
    """A declaration was read with a word of an earlier release (0.2), which this release maps to its 0.3 word. The
    declaration loads; the warning names the old word and the new one, so its source can be converted as touched."""


class LegacyApiWarning(DeprecationWarning):
    """A 0.2 API that 0.3.1 keeps readable (`TableDeclaration.columns`) was used. It works; the warning names what to use
    instead. Removed in a later minor release."""


def _legacy(old: str, new: str, where: str) -> None:
    warnings.warn(f"{where}: '{old}' is a 0.2 word, read as '{new}'; write '{new}' (0.2 words are read for one minor "
                  "release and never written)", LegacyWordWarning, stacklevel=4)


# ── the micro-flow (report-spec-pipeline-model §2, §3, §4, §7) ─────────────────────────────────────────────────────
# Words only: nothing here executes a micro-flow yet (that is step (a″)). They ship so manifests and registries bake
# the right words:
#   spec       := envelope  microflow  formatters
#   microflow  := (routine | producer) processor*
#   routine    := producer+ processor*         (named, reusable; a `step` is a routine deployed to an engine host)
#   formatter  := shape × renderer

#: The parts of a report spec and of what runs it, in the note's words.
STRUCTURE_WORDS = ("spec", "envelope", "microflow", "stage", "producer", "processor", "routine", "formatter", "step")

#: What a micro-flow entry names (§2 `stage := producer | processor | routine`).
STAGE_KINDS = ("producer", "processor", "routine")

#: §3: how a dataset is produced. `typedefs` is new in §10.8 (the Overview's type census).
PRODUCER_KINDS = ("find", "saved_query", "count", "query", "results", "literal", "python", "typedefs")

#: §4: how a dataset is processed.
PROCESSOR_KINDS = ("derive", "aggregate", "join", "snapshot", "filter", "represent")

#: The population a count reads (§3 `count`, §9.23; owner's word 2026-11-06: "population", because `scope` already
#: means the result level, `SCOPES`). `viewer`: every matching element is read and checked, so the count is what the
#: caller may see and agrees with a find (Egeria `pushDown=false`). `repository`: the repository counts rows, fast at
#: any size, with no per-element visibility check (`pushDown=true`).
POPULATIONS = ("viewer", "repository")

# ── fields, shapes and value cells (§5) ─────────────────────────────────────────────────────────────────────────

#: What a field is: plain data; a value cell with companions; a pre-built representation (`mermaidGraph`); nested rows
#: of another shape (master-detail).
FIELD_KINDS = ("data", "cell", "representation", "dataset")

#: The plain field types. `list<T>` and `map<string,T>` take one of these as T; `representation/<format>` is a
#: representation field's type.
FIELD_TYPES = ("string", "int", "float", "fraction", "bool", "datetime", "guid")

#: The companions a value cell may carry (§5 table). `population` is §9.23's count population (see `POPULATIONS`).
CELL_COMPANIONS = ("state", "completeness", "uncertainty", "unit", "as_of", "basis", "provenance", "score",
                   "population")

#: §5 `completeness`, which replaces 0.2's boolean `capped_field`: `complete`; `lower_bound` (what `capped_field`
#: said; rendered "at least N"); `unknown` (silently filtered: not even a bound).
COMPLETENESS = ("complete", "lower_bound", "unknown")

#: How a value that is not `complete` is shown: never a bare integer, never zero (§5).
COMPLETENESS_WORDS = {"lower_bound": "at least {value}", "unknown": "incomplete: some items may be hidden from you"}

#: §5 `uncertainty`: the spread of the value itself (not confidence in the method), in the value's own unit.
UNCERTAINTY_FORMS = ("plus_minus", "low_high", "band")

#: The words for a measure that declares uncertainty whose cell carries none: an absent ± would read as exact.
UNCERTAINTY_ABSENT_WORDS = "spread not estimated"

#: The closed vocabularies a companion's `valid_values` may narrow.
COMPANION_VOCABULARIES = {"state": CELL_STATES, "completeness": COMPLETENESS, "uncertainty": UNCERTAINTY_FORMS,
                          "population": POPULATIONS}

#: A field name: a plain identifier. A dot is always a path (`rows.state`), never part of a name.
FIELD_NAME_PATTERN = r"[A-Za-z_][A-Za-z0-9_]*"

#: §4: a result's confidence is one of five forms, and a score never travels without its basis.
CONFIDENCE_FORMS = ("measured", "estimated", "inferred", "judged", "generated")

#: The forms from strongest to weakest, for §4's "weakest link": a declaration's headline confidence is the weakest
#: of its measures' (project owner, 2026-10-28). A measured read is exact; a judged result carries a person's
#: signature on its evidence; an estimate has a known error; an inferred match a rule or model score; a generated
#: answer is only as good as what it drew on.
CONFIDENCE_STRENGTH = ("measured", "judged", "estimated", "inferred", "generated")

#: §1 `scope`: the level a result is about.
SCOPES = ("resource", "container", "member", "field")

#: The words an extent's truncation sentence must carry for the compiler to fill: "{shown} of {total} ... shown".
TRUNCATION_PLACEHOLDERS = ("{shown}", "{total}")

#: The kinds whose result is its measures: they declare at least one. The other four kinds (finding, proposal, list,
#: table) are told by the block each declares, and a count of what they hold is welcome but not required.
MEASURED_KINDS = ("measure", "series", "distribution", "graph")

#: The kinds that declare how their categories add up (`CategoriesDeclaration`).
CATEGORY_KINDS = ("graph", "distribution")

#: Why a proposal is never decided automatically (owner's rule, 2026-10-15): a proposal becomes a fact only through a
#: person's decision in Curate. `decided_by` keeps "automatic" in its vocabulary so a later ruling can admit it without a
#: model change; until then every annotation type refuses it.
AUTOMATIC_REFUSAL = ("proposals are decided by a person in Curate (ruling 2026-10-15); no automatic path exists, so "
                     "declare decided_by 'curator'")

#: The words a lower bound travels with wherever a figure would be derived from it.
LOWER_BOUND_WORDS = "not derived: the count is a lower bound"

#: The fields a full declaration adds to the minimum, in the order `missing()` names them.
FULL_FIELDS = ("extents", "confidence", "answers", "scope")


def _words(v: str) -> str:
    return " ".join(str(v or "").split())


class _Strict(BaseModel):
    # An unknown key is refused, so a misspelt field is named rather than silently dropped.
    model_config = ConfigDict(extra="forbid")


class AnnotationDeclaration(_Strict):
    """The Egeria annotation a measure writes as (§1 `annotation`), or absent: "generic measure, no native type
    declared" (owner's answer 1). `properties` maps a result field to the Egeria property it is written to; empty
    means the type is declared and its property map is not."""
    type: str
    properties: dict[str, str] = _Default(default_factory=dict)

    @field_validator("type")
    @classmethod
    def _type(cls, v: str) -> str:
        if not _words(v):
            raise ValueError("annotation type is empty: name the Egeria annotation type, or leave annotation out "
                             "for a generic measure")
        return _words(v)


class BasisDeclaration(_Strict):
    """The whole a counted measure is a part of: "456 of 1,236 columns" is derived from the measure's value and this
    denominator, so no reader writes the "of" in prose. Legal only on a count; a fraction's whole is in its unit."""
    #: The result field holding the whole ("column_count"); a dotted path or a trailing `[]`, as `value_field`.
    denominator_field: str
    #: The whole in words, plural: "columns", "tables in the schema", "rows read".
    denominator_label: str

    @model_validator(mode="after")
    def _filled(self) -> "BasisDeclaration":
        if not _words(self.denominator_field):
            raise ValueError("a basis names no denominator_field: say which result field holds the whole")
        if not _words(self.denominator_label):
            raise ValueError("a basis declares no words for the whole (denominator_label): say what is counted, "
                             "plural, such as 'columns'")
        return self


def is_fraction(unit: str) -> bool:
    """Does this unit say a fraction, ratio or percentage, rather than a count of things? (Its whole is in its words.)"""
    u = " ".join(str(unit or "").lower().split())
    return u.startswith(("fraction", "ratio", "percent", "share", "proportion")) or "(0-1)" in u or "%" in u


class MeasureDeclaration(_Strict):
    """One number the analysis reports. A number never travels without its unit and its as-of (§1)."""
    name: str
    #: In words, plural where it counts things: "tables", "rows per day", "days", "fraction of rows (0-1)".
    unit: str
    #: The result field that says when this was measured ("asOf", "surveyed_at", "toAsOf"). A dotted path names a
    #: nested field ("temporal.as_of"); `run.<field>` names a field of the run that produced the result rather than
    #: of the result itself (`run.read_snapshot`: the newest stored row a zero-fetch derivation read).
    as_of: str
    #: The result field holding the value; a dotted path names a nested one ("counts.stale"), and a trailing `[]`
    #: declares the value as the number of items in a list field ("columns_added[]": columns added, counted).
    value_field: str
    #: What it writes as in Egeria; absent is the generic measure route, labelled as such.
    annotation: AnnotationDeclaration | None = None
    #: This measure's own confidence, where it differs from the declaration's (project owner, 2026-10-28: confidence
    #: is per measure). Absent means the declaration's confidence is this measure's.
    confidence: "ConfidenceDeclaration | None" = None
    #: The level THIS measure is about, where it differs from the declaration's (a member-scoped step whose summary
    #: is one value for the whole resource). Absent means the declaration's scope is this measure's.
    scope: Literal["resource", "container", "member", "field"] | None = None
    #: The whole this count is a part of; absent for a count with no stated whole.
    basis: BasisDeclaration | None = None
    #: The result field saying how complete the value is (§5 `completeness`, replacing 0.2's `capped_field`): it holds
    #: one of `COMPLETENESS`, or a boolean read as `lower_bound` when true and `complete` when false (so the 0.2
    #: `capped` fields keep their meaning; `completeness_of`). Declared on the measure, not the declaration, because
    #: one step may cap one measure (a paged list) and not another (a COUNT(*)). A `lower_bound` value reads "at least N
    #: <unit>" and every figure derived from it is withheld. Empty: the value is not declared as possibly incomplete.
    completeness_field: str = ""
    #: The spread of the value (§5 `uncertainty`), declared with its form; never on an exact count, whose only
    #: uncertainty is its completeness.
    uncertainty: "UncertaintyDeclaration | None" = None

    @model_validator(mode="before")
    @classmethod
    def _legacy_capped_field(cls, data):
        if isinstance(data, dict) and "capped_field" in data:
            data = dict(data)
            capped = data.pop("capped_field")
            if _words(data.get("completeness_field")) and _words(capped) != _words(data["completeness_field"]):
                raise ValueError(f"measure '{data.get('name', '')}' declares capped_field and completeness_field: "
                                 "capped_field is the 0.2 word for completeness_field, so declare completeness_field "
                                 "only")
            data["completeness_field"] = capped
            _legacy("capped_field", "completeness_field", f"measure '{data.get('name', '')}'")
        return data

    @property
    def capped_field(self) -> str:
        """0.2's name for `completeness_field`, for readers not yet converted. Read-only; warns."""
        _legacy("capped_field", "completeness_field", f"measure '{self.name}'")
        return self.completeness_field

    def is_count(self) -> bool:
        """Is this a count of things, by what the declaration itself says: a basis (legal only on a count) or a value
        that is the number of items in a list (`value_field` ending `[]`)?"""
        return self.basis is not None or self.value_field.strip().endswith("[]")

    @field_validator("scope", mode="before")
    @classmethod
    def _scope(cls, v):
        if v is not None and v not in SCOPES:
            raise ValueError(f"scope '{v}' is not one of the levels ({', '.join(SCOPES)})")
        return v

    @model_validator(mode="after")
    def _basis_is_on_a_count(self) -> "MeasureDeclaration":
        if self.basis is not None and is_fraction(self.unit):
            raise ValueError(f"measure '{self.name}' declares a basis on a fraction ('{self.unit}'): the "
                             "denominator is in the unit, so a basis belongs on a count only")
        if self.uncertainty is not None and self.is_count():
            raise ValueError(f"measure '{self.name}' declares uncertainty on a count: a count is exact, and its only "
                             "uncertainty is its completeness, so declare completeness_field instead")
        return self

    @model_validator(mode="after")
    def _filled(self) -> "MeasureDeclaration":
        empty = [f for f in ("name", "unit", "as_of", "value_field") if not _words(getattr(self, f))]
        if empty:
            label = f"measure '{self.name}'" if _words(self.name) else "a measure"
            raise ValueError(f"{label} declares no {', '.join(empty)}: a number never travels without its unit "
                             "and its as-of")
        return self


def completeness_of(value) -> str:
    """A result's completeness value as one of `COMPLETENESS`: a word as itself, a boolean (0.2's `capped`) as
    `lower_bound` when true and `complete` when false, anything else `unknown` (never silently `complete`)."""
    if isinstance(value, bool):
        return "lower_bound" if value else "complete"
    word = _words(value)
    return word if word in COMPLETENESS else "unknown"


class UncertaintyDeclaration(_Strict):
    """§5 `uncertainty`: the spread of a measure's value, in the value's own unit, distinct from confidence in the
    method. Declared per measure; filled per cell. A cell that carries none reads `UNCERTAINTY_ABSENT_WORDS`."""
    form: str
    #: The result field holding the spread: the ± for `plus_minus`, the band's name for `band`.
    field: str = ""
    #: `low_high` only: the result fields holding the low and the high value.
    low_field: str = ""
    high_field: str = ""

    @model_validator(mode="after")
    def _form(self) -> "UncertaintyDeclaration":
        if self.form not in UNCERTAINTY_FORMS:
            raise ValueError(f"uncertainty form '{self.form}' is not one of the forms ({', '.join(UNCERTAINTY_FORMS)})")
        if self.form == "low_high":
            if not (_words(self.low_field) and _words(self.high_field)) or _words(self.field):
                raise ValueError("uncertainty form 'low_high' names low_field and high_field (and no field): say "
                                 "which result fields hold the low and the high value")
        elif not _words(self.field) or _words(self.low_field) or _words(self.high_field):
            raise ValueError(f"uncertainty form '{self.form}' names field (and no low_field or high_field): say which "
                             "result field holds the spread")
        return self


class AbsenceSentences(_Strict):
    """§1 `absence`: the sentence shown for each way a result can be absent. All four are declared.

    0.2's `measured_nothing` is read as `nothing_found` (with a `LegacyWordWarning`) and never written."""
    not_measured: str
    not_permitted: str
    not_applicable: str
    nothing_found: str

    @model_validator(mode="before")
    @classmethod
    def _legacy_words(cls, data):
        if not isinstance(data, dict):
            return data
        data = dict(data)
        for old, new in LEGACY_ABSENCE_WORDS.items():
            if old not in data:
                continue
            sentence = data.pop(old)
            if new in data and _words(data[new]) != _words(sentence):
                raise ValueError(f"absence declares {old} and {new} with different sentences: {old} is the 0.2 word "
                                 f"for {new}, so declare {new} only")
            data[new] = sentence
            _legacy(old, new, "absence")
        return data

    @model_validator(mode="after")
    def _filled(self) -> "AbsenceSentences":
        empty = [s for s in ABSENCE_STATES if not _words(getattr(self, s))]
        if empty:
            raise ValueError(f"absence sentence for {', '.join(empty)} is empty: an absence is declared, never "
                             "improvised")
        return self

    def sentence(self, state: str) -> str:
        """The sentence for an absence state; a 0.2 word (`measured_nothing`) gives its 0.3 word's sentence, and warns."""
        if state in LEGACY_ABSENCE_WORDS:
            _legacy(state, LEGACY_ABSENCE_WORDS[state], "absence.sentence")
            state = LEGACY_ABSENCE_WORDS[state]
        return getattr(self, state)


class ExtentDeclaration(_Strict):
    """§3 step 2: one shape the Chat compiler may take from this analysis, and no other."""
    name: str
    fields: list[str]
    #: How many rows the extent carries at most.
    rows: int
    #: The order rows are taken in, in words ("PUBLIC grantees first, then by table"), for an order no `sort` can
    #: say. Not declared beside `sort`: the order is said in one place.
    order: str = ""
    #: The order as keys the compiler applies, each "<field> asc" or "<field> desc" on one of `fields`, first key
    #: first ("row_count desc"); the words are derived from it (`order_words`). Project owner, 2026-10-28.
    sort: list[str] = _Default(default_factory=list)
    #: Shown when rows were dropped; carries `{shown}` and `{total}` for the compiler to fill.
    truncation: str
    #: The extent's cost at `rows` rows, in tokens, for the compiler's budget (§3 step 4).
    token_cost: int
    #: About how many tokens ONE row costs, so the compiler can quote a prefix within its budget ("N of M rows
    #: quoted"). Set on the extent a table derives (fields x `TOKENS_PER_CELL`); 0 on a hand-written extent, which
    #: is priced whole.
    token_cost_per_row: int = 0
    #: How an answer cites a row of this extent ("{analysis} · {scope} · as of {as_of}").
    citation: str
    #: Where the rows are in the result, when that is not a field named like the extent: each a dotted path to a
    #: list (each item a row) or to a mapping (one row), "." the result itself as one row. Several are joined in
    #: order. Empty means the extent's name is the path.
    source: list[str] = _Default(default_factory=list)
    #: With several sources: the row field that carries which source a row came from (the path's last part:
    #: "columns_added"), so joined rows stay told apart. Empty for none.
    tag: str = ""

    @field_validator("source", "sort", mode="before")
    @classmethod
    def _one_item(cls, v):
        return [v] if isinstance(v, str) else v

    def sort_keys(self) -> list[tuple[str, bool]]:
        """`sort` as (field, descending) pairs, first key first."""
        out = []
        for key in self.sort:
            field, _, direction = " ".join(key.split()).rpartition(" ")
            out.append((field, direction == "desc"))
        return out

    def order_words(self) -> str:
        """The order in words: derived from `sort` when it is declared, else the declared sentence."""
        if not self.sort:
            return self.order
        return "by " + ", then ".join(f"{f}, {'descending' if d else 'ascending'}" for f, d in self.sort_keys())

    @model_validator(mode="after")
    def _shape(self) -> "ExtentDeclaration":
        label = f"extent '{self.name}'" if _words(self.name) else "an extent"
        if not _words(self.name):
            raise ValueError("an extent declares no name")
        if any(not _words(s) for s in self.source):
            raise ValueError(f"{label} declares an empty source path")
        if _words(self.tag) and _words(self.tag) not in self.fields:
            raise ValueError(f"{label} tags its rows with '{self.tag}', which is not one of its fields: the tag is "
                             "how the rows are told apart, so the compiler must show it")
        if not [f for f in self.fields if _words(f)]:
            raise ValueError(f"{label} declares no fields: the compiler takes the declared fields and no others")
        if self.rows < 1:
            raise ValueError(f"{label} declares rows {self.rows}: an extent carries at least one row")
        if self.token_cost < 1:
            raise ValueError(f"{label} declares token_cost {self.token_cost}: the compiler budgets by it, so it "
                             "must be a positive estimate")
        if not _words(self.citation):
            raise ValueError(f"{label} declares no citation")
        if self.sort and _words(self.order):
            raise ValueError(f"{label} declares both sort and order: the order is said in one place, so leave the "
                             "order sentence out and it is derived from sort")
        if not self.sort and not _words(self.order):
            raise ValueError(f"{label} declares no order: declare sort keys, or the order in words when no key "
                             "can say it")
        for key in self.sort:
            field, _, direction = " ".join(key.split()).rpartition(" ")
            if direction not in ("asc", "desc") or not field:
                raise ValueError(f"{label} sort key '{key}' is not '<field> asc' or '<field> desc'")
            if field not in self.fields:
                raise ValueError(f"{label} sorts by '{field}', which is not one of its fields")
        lacking = [p for p in TRUNCATION_PLACEHOLDERS if p not in self.truncation]
        if lacking:
            raise ValueError(f"{label} truncation sentence '{self.truncation}' lacks {', '.join(lacking)}: it says "
                             "how many rows were shown of how many")
        return self


class ConfidenceDeclaration(_Strict):
    """§4: the form, and the result field that carries its basis. A score never travels without its basis."""
    form: str
    #: The result field carrying the basis: the method or sample ratio (estimated), the rules that matched
    #: (inferred), who and on what evidence (judged), the sources drawn on (generated). Empty for `measured`, whose
    #: basis is its as-of and scope.
    basis: str = ""
    #: The basis in words, which is what a person reads beside the form. Required whenever `basis` names a result
    #: field (a field path is for the code, not the reader); alone it stands for a basis no result field carries: an estimate's
    #: source ("pg_stat_user_tables.n_live_tup, the statistics collector's live-row estimate"). An estimated or
    #: generated result declares a basis field, a method, or both; an inferred or judged one needs its basis field,
    #: because its basis differs per result.
    method: str = ""
    #: The result field carrying the score, for an inferred result; empty where there is none.
    score: str = ""
    #: Inferred only, and required there (§4 "calibration is stated"): is the score a calibrated probability, or a
    #: rule count?
    calibrated: bool | None = None

    @model_validator(mode="after")
    def _form(self) -> "ConfidenceDeclaration":
        if self.form not in CONFIDENCE_FORMS:
            raise ValueError(f"confidence form '{self.form}' is not one of the five forms "
                             f"({', '.join(CONFIDENCE_FORMS)})")
        if self.form in ("inferred", "judged") and not _words(self.basis):
            raise ValueError(f"confidence form '{self.form}' declares no basis: a score never travels without "
                             "its basis, and this form's basis differs per result, so name the field carrying it")
        if self.form in ("estimated", "generated") and not (_words(self.basis) or _words(self.method)):
            raise ValueError(f"confidence form '{self.form}' declares no basis and no method: say how the number "
                             "was arrived at")
        if self.form == "measured" and (_words(self.score) or self.calibrated is not None):
            raise ValueError("confidence form 'measured' declares a score: an exact read has none, because none "
                             "is meaningful")
        if self.form == "inferred" and self.calibrated is None:
            raise ValueError("confidence form 'inferred' does not say whether its score is calibrated: state "
                             "calibrated true (a probability) or false (a rule count)")
        if self.form != "inferred" and self.calibrated is not None:
            raise ValueError(f"confidence form '{self.form}' declares calibrated: only an inferred score is "
                             "calibrated or not")
        if _words(self.basis) and not _words(self.method):
            raise ValueError(f"confidence basis '{self.basis}' names a result field and no method: a person reads "
                             "the method, never a field path, so say the basis in words")
        return self


class CategoriesDeclaration(_Strict):
    """How a graph's or distribution's categories relate (the #603 lesson: categories that overlap must not be
    stacked or summed, and a stated total is read, never added up on the client)."""
    #: True: one item falls in exactly one category. False: an item may fall in several, so a renderer must not stack
    #: or sum the categories and the headline may not say "of N".
    exclusive: bool
    #: The result field holding the stated total the categories add up to; "" for no stated total.
    sums_to: str = ""

    @model_validator(mode="after")
    def _sums(self) -> "CategoriesDeclaration":
        if _words(self.sums_to) and not self.exclusive:
            raise ValueError("categories declare a total (sums_to) and are not exclusive: overlapping categories "
                             "cannot sum to a total, so leave sums_to out or declare them exclusive")
        return self


class FindingDeclaration(_Strict):
    """A finding: a sentence a person reads, about a place, with a severity and perhaps an action."""
    #: The field holding the sentence a person reads ("summary").
    what_field: str
    #: The field naming the place (scope, column, path); "" for a finding about the resource as a whole.
    where_field: str = ""
    severity_field: str = ""
    #: The closed vocabulary `severity_field` may hold, in words, lowest to highest.
    severities: list[str] = _Default(default_factory=list)
    #: The field saying what to do, when the finding proposes an action (published as a RequestForAction).
    action_field: str = ""

    @model_validator(mode="after")
    def _shape(self) -> "FindingDeclaration":
        if not _words(self.what_field):
            raise ValueError("a finding declares no what_field: name the result field holding the sentence a "
                             "person reads")
        if _words(self.severity_field) and not [s for s in self.severities if _words(s)]:
            raise ValueError("a finding declares a severity_field and no severities: list the words it may hold, "
                             "lowest to highest")
        if [s for s in self.severities if _words(s)] and not _words(self.severity_field):
            raise ValueError("a finding declares severities and no severity_field: name the field that holds them")
        return self


class ProposalDeclaration(_Strict):
    """A proposal: a candidate value someone decides on. A proposal is never a fact until it is decided."""
    #: The field holding the proposed value(s).
    candidate_field: str
    #: Who turns it into a fact (owner rule: facts only through Curate).
    decided_by: Literal["curator", "automatic"]
    decision_states: list[str] = _Default(default_factory=lambda: ["proposed", "accepted", "rejected"])
    #: The field of each candidate row holding its decision state, when rows carry one; "" means every candidate
    #: is still a proposal.
    state_field: str = ""

    @model_validator(mode="after")
    def _shape(self) -> "ProposalDeclaration":
        if not _words(self.candidate_field):
            raise ValueError("a proposal declares no candidate_field: name the result field holding what is proposed")
        states = [_words(s) for s in self.decision_states]
        if not states or any(not s for s in states):
            raise ValueError("a proposal declares no decision_states, or an empty one: say the states a decision "
                             "moves through, starting with 'proposed'")
        if states[0] != "proposed":
            raise ValueError("a proposal's first decision state is not 'proposed': a candidate starts as a proposal")
        return self


class ListDeclaration(_Strict):
    """A list: items in an order, each told apart by a key."""
    #: The fields a row shows, in order.
    item_fields: list[str]
    #: In words: "largest first".
    order: str
    #: What makes an item one item.
    key_field: str
    #: What the items are, plural, in words ("tables needing attention"), where the key field's name reads badly as
    #: one; empty means the key field's name, spaced.
    item_label: str = ""

    @model_validator(mode="after")
    def _shape(self) -> "ListDeclaration":
        if not [f for f in self.item_fields if _words(f)]:
            raise ValueError("a list declares no item_fields: name the fields a row shows, in order")
        if not _words(self.order):
            raise ValueError("a list declares no order: say it in words, such as 'largest first'")
        if not _words(self.key_field):
            raise ValueError("a list declares no key_field: name what makes an item one item")
        return self


# ── state sets (§5 "What a field declares") ─────────────────────────────────────────────────────────────────────

class StateSet(_Strict):
    """A named narrowing of the shared cell states: a field's `state` companion may name one so its cells hold only
    these words. A set only narrows (it is a subset of `CELL_STATES`), never adds a word, because formatters and
    absence sentences know only the shared words."""
    name: str
    states: tuple[str, ...]

    @model_validator(mode="after")
    def _subset(self) -> "StateSet":
        if not re.fullmatch(FIELD_NAME_PATTERN, self.name or ""):
            raise ValueError(f"state set name '{self.name}' is not an identifier")
        if not self.states:
            raise ValueError(f"state set '{self.name}' names no states")
        if len(set(self.states)) != len(self.states):
            raise ValueError(f"state set '{self.name}' names a state more than once")
        extra = [s for s in self.states if s not in CELL_STATES]
        if extra:
            raise ValueError(f"state set '{self.name}' names {', '.join(extra)}, which is not a cell state "
                             f"({', '.join(CELL_STATES)}): a set narrows the shared words, never adds one")
        return self


#: The registered state sets, by name. `CountStates`: a count read under the daemon cannot be `not_permitted`.
#: `MemberStates`: one member of a resource read on its own, which may be refused (B1's per-row states, renamed).
STATE_SETS: dict[str, StateSet] = {}


def register_state_set(name: str, states) -> StateSet:
    """Register a state set (validated: an identifier, a subset of `CELL_STATES`). Re-registering the same states is a
    no-op; different states under a registered name are refused."""
    s = StateSet(name=name, states=tuple(states))
    if name in STATE_SETS and STATE_SETS[name] != s:
        raise ValueError(f"state set '{name}' is registered with other states ({', '.join(STATE_SETS[name].states)})")
    STATE_SETS[name] = s
    return s


CountStates = register_state_set("CountStates", ("measured", "not_measured", "nothing_found")).states
MemberStates = register_state_set("MemberStates", ("measured", "not_measured", "not_permitted", "nothing_found")).states


# ── fields and shapes (§5) ──────────────────────────────────────────────────────────────────────────────────────

_SCALAR = "|".join(FIELD_TYPES)
_TYPE_PATTERN = re.compile(rf"(?:{_SCALAR})|list<(?:{_SCALAR})>|map<\s*string\s*,\s*(?:{_SCALAR})\s*>|"
                           r"representation/[A-Za-z0-9_.-]+")


class Companion(_Strict):
    """A companion a cell carries, with the named set (or the list) its value is narrowed to."""
    name: str
    valid_values: str | list[str] | None = None


class Field(_Strict):  # noqa: F811 (pydantic's Field is imported as _Default)
    """One field (§5), declared in exactly one place: the `out` of the stage that produces it, or a registered shape.

    `name` is the data key, an identifier (a dot is a path); `label` the column name shown. A `cell` is a value with
    companions (`state`, `completeness`, ...); a cell with no companions list carries `state` only. A `dataset` is
    nested rows of the `shape` it names. A `representation` is a pre-built rendering of `type`
    `representation/<format>` (or `format`, the note's short spelling)."""
    name: str
    label: str = ""
    kind: Literal["data", "cell", "representation", "dataset"] = "data"
    type: str = ""
    unit: str = ""
    #: The spec a click on the field drills into.
    detail_spec: str = ""
    #: A data field's allowed values, or the name of a registered value set.
    valid_values: str | list[str] | None = None
    #: `dataset` only: the registered shape of its rows.
    shape: str = ""
    #: `cell` only: each a companion name (any value of its shared vocabulary) or `{name, valid_values}`.
    companions: list[str | Companion] | None = None
    #: `representation` only: the short spelling of `type: representation/<format>`.
    format: str = ""
    #: A table's `cell` column only: the measure the column is the per-member value of. Required there (the absence
    #: sentence comes from the measure), ignored on any other field.
    measure: str = ""

    @model_validator(mode="before")
    @classmethod
    def _short_forms(cls, data):
        if isinstance(data, dict) and data.get("kind") == "representation" and data.get("format") and not data.get("type"):
            data = {**data, "type": f"representation/{data['format']}"}
        return data

    @model_validator(mode="after")
    def _shape(self) -> "Field":
        if not re.fullmatch(FIELD_NAME_PATTERN, self.name or ""):
            why = "a dot is a path, never part of a name" if "." in (self.name or "") else \
                f"a field name matches {FIELD_NAME_PATTERN}"
            raise ValueError(f"field name '{self.name}' is not an identifier: {why}")
        label = f"field '{self.name}'"
        if not _words(self.label):
            if self.kind != "representation":
                raise ValueError(f"{label} declares no label: say the column name a person reads")
            self.label = self.name
        if self.kind == "dataset":
            if not _words(self.shape):
                raise ValueError(f"{label} is a dataset and names no shape: a list of rows is a dataset of a shape")
            if _words(self.type):
                raise ValueError(f"{label} is a dataset and declares type '{self.type}': its rows' shape is its type")
        else:
            if _words(self.shape):
                raise ValueError(f"{label} names a shape and is a '{self.kind}' field: a shape belongs to a dataset")
            if not _words(self.type):
                raise ValueError(f"{label} declares no type ({', '.join(FIELD_TYPES)}, list<T>, map<string,T>)")
            if not _TYPE_PATTERN.fullmatch(self.type):
                raise ValueError(f"{label} type '{self.type}' is not a field type ({', '.join(FIELD_TYPES)}, "
                                 "list<T>, map<string,T>, representation/<format>)")
            is_rep = self.type.startswith("representation/")
            if is_rep != (self.kind == "representation"):
                raise ValueError(f"{label} is a '{self.kind}' field of type '{self.type}': a representation field, "
                                 "and only one, has type representation/<format>")
        if _words(self.format) and self.type != f"representation/{self.format}":
            raise ValueError(f"{label} declares format '{self.format}' and type '{self.type}': format is the short "
                             "spelling of a representation field's type")
        if self.companions is not None and self.kind != "cell":
            raise ValueError(f"{label} declares companions and is a '{self.kind}' field: companions belong to a cell")
        self.companions = [Companion(name=c) if isinstance(c, str) else c for c in self.companions] \
            if self.companions is not None else None
        names = [c.name for c in self.companions or []]
        unknown = [n for n in names if n not in CELL_COMPANIONS]
        if unknown:
            raise ValueError(f"{label} declares companion {', '.join(unknown)}, which is not a cell companion "
                             f"({', '.join(CELL_COMPANIONS)})")
        if len(set(names)) != len(names):
            raise ValueError(f"{label} declares a companion more than once")
        for c in self.companions or []:
            if c.valid_values is not None:
                _check_narrowing(label, c)
        return self

    def companion_names(self) -> list[str]:
        """The companions a cell of this field carries: `state` only when it declares no list; none for a non-cell."""
        if self.kind != "cell":
            return []
        return ["state"] if self.companions is None else [c.name for c in self.companions]

    def states(self) -> tuple[str, ...]:
        """The states a cell of this field may hold: its `state` companion's set, else every cell state."""
        state = next((c for c in self.companions or [] if c.name == "state"), None)
        if state is None or state.valid_values is None:
            return CELL_STATES
        return STATE_SETS[state.valid_values].states if isinstance(state.valid_values, str) else tuple(state.valid_values)


def _check_narrowing(label: str, c: Companion) -> None:
    """At load (§2c): a companion's named set exists and is a subset of its shared vocabulary."""
    vocabulary = COMPANION_VOCABULARIES.get(c.name)
    if vocabulary is None:
        raise ValueError(f"{label} narrows companion '{c.name}', which has no closed vocabulary to narrow "
                         f"(only {', '.join(COMPANION_VOCABULARIES)} do)")
    if isinstance(c.valid_values, str):
        if c.name != "state":
            raise ValueError(f"{label} names a set for companion '{c.name}': only state sets are registered; list "
                             "the values")
        if c.valid_values not in STATE_SETS:
            raise ValueError(f"{label} names state set '{c.valid_values}', which is not registered "
                             f"({', '.join(STATE_SETS)})")
        values = STATE_SETS[c.valid_values].states
    else:
        values = tuple(c.valid_values)
    extra = [v for v in values if v not in vocabulary]
    if not values or extra:
        raise ValueError(f"{label} narrows '{c.name}' to {', '.join(extra) or 'nothing'}, which is not a subset of "
                         f"its words ({', '.join(vocabulary)})")


class FieldInclude(_Strict):
    """A shape entry that reuses one field of another shape (`{"include": "CommonRow.description"}`), in its place."""
    include: str

    @model_validator(mode="after")
    def _path(self) -> "FieldInclude":
        if not re.fullmatch(rf"{FIELD_NAME_PATTERN}\.{FIELD_NAME_PATTERN}", self.include or ""):
            raise ValueError(f"include '{self.include}' is not '<Shape>.<field>'")
        return self


class Shape(_Strict):
    """A registered shape (§5): the fields it declares, plus those it reuses. `extends` reuses every field of the parent
    shape, first; an `include` entry reuses one field of another shape, in its place. A reused field is the declarer's
    one field (one `DataField` in Egeria), never a copy: a shape may not redeclare a field it reuses."""
    fields: list[Field | FieldInclude] = _Default(default_factory=list)
    extends: str = ""

    @field_validator("fields", mode="before")
    @classmethod
    def _entries(cls, v):
        if isinstance(v, list):
            return [FieldInclude.model_validate(e) if isinstance(e, dict) and "include" in e else e for e in v]
        return v

    def declared(self) -> list[Field]:
        return [f for f in self.fields if isinstance(f, Field)]


#: The registered shapes, by name (the registry's CONFIG tier, §5 "Registered shapes replace the Python column
#: constants"). A table names one by `shape`; a dataset field by its `shape`.
SHAPES: dict[str, Shape] = {}


def register_shape(name: str, shape: "Shape | dict") -> Shape:
    """Register a shape, checked against the registry: its parent and includes exist, and it declares no field it
    reuses (§5 "Field names are shared, not copied"). Re-registering an equal shape is a no-op."""
    if not re.fullmatch(FIELD_NAME_PATTERN, name or ""):
        raise ValueError(f"shape name '{name}' is not an identifier")
    s = shape if isinstance(shape, Shape) else Shape.model_validate(shape)
    if name in SHAPES:
        if SHAPES[name] != s:
            raise ValueError(f"shape '{name}' is registered with other fields")
        return s
    resolve_fields(s, name)   # refuses what does not resolve
    SHAPES[name] = s
    return s


def resolve_fields(shape: "Shape | str", name: str = "") -> list[tuple[str, Field]]:
    """A shape's fields in order, each with the shape that declares it: the parent's (recursively), then its own
    entries. Refuses an unknown parent or include, a cycle, and a field declared twice or redeclared."""
    return _resolve(shape, name, ())


def _resolve(shape, name: str, seen: tuple[str, ...]) -> list[tuple[str, Field]]:
    if isinstance(shape, str):
        name = shape
        if name not in SHAPES:
            raise ValueError(f"shape '{name}' is not registered")
        shape = SHAPES[name]
    if name and name in seen:
        raise ValueError(f"shape '{name}' extends itself ({' -> '.join(seen + (name,))})")
    seen = seen + ((name,) if name else ())
    out: list[tuple[str, Field]] = []
    if _words(shape.extends):
        if shape.extends not in SHAPES:
            raise ValueError(f"shape '{name}' extends '{shape.extends}', which is not registered")
        out += _resolve(shape.extends, shape.extends, seen)
    for entry in shape.fields:
        if isinstance(entry, FieldInclude):
            owner, _, field = entry.include.partition(".")
            if owner not in SHAPES:
                raise ValueError(f"shape '{name}' includes {entry.include}: shape '{owner}' is not registered")
            found = next(((d, f) for d, f in _resolve(owner, owner, seen) if f.name == field), None)
            if found is None:
                raise ValueError(f"shape '{name}' includes {entry.include}: '{owner}' has no field '{field}'")
            out.append(found)
        else:
            out.append((name, entry))
    names = [f.name for _, f in out]
    for n in sorted({n for n in names if names.count(n) > 1}):
        declarers = [d or "(inline)" for d, f in out if f.name == n]
        raise ValueError(f"shape '{name or '(inline)'}' has field '{n}' more than once (declared by "
                         f"{', '.join(declarers)}): a reused field is shared, never redeclared")
    return out


# ── the table (B1, re-expressed on §5) ──────────────────────────────────────────────────────────────────────────

#: B1's (0.2) column types, read for one minor release: each -> the §5 field type and, for a number that says its
#: unit in its type, that unit. `state` is not a field type in 0.3 (`TableDeclaration`, legacy read).
LEGACY_COLUMN_TYPES = {"text": ("string", ""), "integer": ("int", ""), "number": ("float", ""),
                       "boolean": ("bool", ""), "date": ("datetime", ""), "datetime": ("datetime", ""),
                       "bytes": ("int", "bytes"), "duration": ("float", "seconds"), "state": ("string", "")}

#: B1 (DESIGN-B1-MEMBER-SCOPED-TABLE-RESULT §2, 0.2): the types a table column may hold. Read only.
TABLE_COLUMN_TYPES = tuple(LEGACY_COLUMN_TYPES)

#: The owner's cap on the rows a table shows (ruling 2026-11-02, "1,000"): a declaration may lower it, never raise it.
#: Every row is stored; the cap is for showing.
TABLE_MAX_ROWS = 1000

#: About how many tokens one cell of a table costs a chat compile, for the extent a table derives
#: (`TableDeclaration.extent`): the catalogue's hand-priced extents run 7-9 per cell. An estimate, so wherever a cost
#: derived from it is shown it is said with "about" (Architect ruling, 2026-11-02).
TOKENS_PER_CELL = 8

#: The scopes at which a table is about MEMBERS of a resource, so its rows need a key (§2 rule 1).
KEYED_SCOPES = ("member", "field")


def _label(name: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in name.replace("_", " ").split())


#: The reverse of `LEGACY_COLUMN_TYPES`, for the compat `TableDeclaration.columns`: (§5 type, unit) -> 0.2 type. The
#: unit-implying types are listed first so `int`+`bytes` is `bytes`, not `integer`. `date` -> `datetime` is lossy.
_REVERSE_COLUMN_TYPES = {("int", "bytes"): "bytes", ("float", "seconds"): "duration", ("string", ""): "text",
                         ("int", ""): "integer", ("float", ""): "number", ("bool", ""): "boolean",
                         ("datetime", ""): "datetime"}


@dataclass(frozen=True)
class LegacyColumn:
    """A 0.2 table column as `TableDeclaration.columns` returns it: `name`, `type` (a 0.2 type), `unit`, `absence`,
    `states` and `key`, read only."""
    name: str
    type: str
    unit: str = ""
    absence: str = ""
    states: tuple[str, ...] = ()
    key: bool = False


class TableColumn(_Strict):
    """A B1 (0.2) table column, read only: `TableDeclaration` converts each to a `Field` (`as_field`) and
    writes fields. Kept so a 0.2 column is refused with the sentence it was refused with."""
    name: str
    type: str = "text"
    unit: str = ""
    absence: str = ""
    states: list[str] = _Default(default_factory=list)
    measure_ref: str = ""

    @model_validator(mode="after")
    def _shape(self) -> "TableColumn":
        if not _words(self.name):
            raise ValueError("a table column declares no name")
        label = f"table column '{self.name}'"
        if self.type not in TABLE_COLUMN_TYPES:
            raise ValueError(f"{label} type '{self.type}' is not one of the column types "
                             f"({', '.join(TABLE_COLUMN_TYPES)})")
        if self.type in ("number", "bytes", "duration") and not _words(self.unit):
            raise ValueError(f"{label} is a {self.type} column with no unit: a number never travels without its unit")
        states = [s for s in self.states if _words(s)]
        if self.type == "state" and not states:
            raise ValueError(f"{label} is a state column and declares no states: list the words it may hold")
        if self.type != "state" and self.states:
            raise ValueError(f"{label} declares states and type '{self.type}': states belong to a state column")
        if len(states) != len(set(states)):
            raise ValueError(f"{label} declares a state more than once")
        return self

    def as_field(self) -> dict:
        """The §5 field this column is (the reconciliation table of BRIEF RS-W1-1 §2): types renamed, the unit a type
        implied made explicit, the per-column absence word dropped (it is the measure's), `measure_ref` -> `measure`
        on a cell. A 0.2 `state` column is read as a string field whose `valid_values` is the registered state set
        its (renamed) states equal, else the list itself; a 0.3 table carries state as a cell's companion instead."""
        ftype, unit = LEGACY_COLUMN_TYPES[self.type]
        out: dict = {"name": self.name, "label": _label(self.name), "type": ftype}
        if _words(self.unit) or unit:
            out["unit"] = _words(self.unit) or unit
        if self.type == "state":
            states = tuple(LEGACY_ABSENCE_WORDS.get(s, s) for s in self.states)
            named = next((n for n, s in STATE_SETS.items() if set(s.states) == set(states)), None)
            out["valid_values"] = named or list(states)
        if _words(self.measure_ref):
            out.update(kind="cell", measure=self.measure_ref)
        return out


class TableDeclaration(_Strict):
    """A table: rows about MEMBERS of a resource (columns, files, datasets), each row keyed by what makes the member one
    member, with typed fields, a size the declaration caps and a summary it states (DESIGN-B1 §2). A table with no key
    is a table of one row (the resource as a whole).

    Since 0.3 a table's rows are a §5 dataset: its fields are a registered `shape` (the normal case, so Egeria gets one
    `DataStructure`) or inline `fields`. The table-level rules (key, cap, order, truncation, summary) stay here. A 0.2
    `columns` list is read with a `LegacyWordWarning` and written as `fields`.

    Every row is stored; `max_rows` is how many are SHOWN, and `truncation` says how many were not: the shown slice is a
    dataset whose completeness is `lower_bound` when truncated. The summary measures are computed by the step over all
    rows and declared beside the table, never added up from the shown slice."""
    #: The registered shape of a row (`SHAPES`); empty when the fields are inline.
    shape: str = ""
    #: The row's fields, inline; empty when `shape` names them.
    fields: list[Field] = _Default(default_factory=list)
    #: The fields that make a row one row; required at member or field scope, empty for a table of one row.
    key_fields: list[str] = _Default(default_factory=list)
    #: How many rows are shown, at most: the owner's cap, `TABLE_MAX_ROWS`, which a declaration may only lower.
    max_rows: int = TABLE_MAX_ROWS
    #: The order rows are shown in, in words ("schema, table, column as the catalog lists them").
    order: str = ""
    #: Shown with the table; carries `{shown}` and `{total}` ("the first {shown} of {total} columns; every column is
    #: stored and the summary counts them all").
    truncation: str = ""
    #: The measures, declared beside the table, that say the whole of it in one sentence; required at member scope.
    summary: list[str] = _Default(default_factory=list)
    #: The per-column `absence` text a 0.2 `columns` list declared, by column name: kept so `columns` reads it back
    #: (0.3.1). Not written (`model_dump` leaves it out); a 0.3 table has none.
    legacy_absence: dict[str, str] = _Default(default_factory=dict, exclude=True, repr=False)

    @model_validator(mode="before")
    @classmethod
    def _legacy_columns(cls, data):
        if not isinstance(data, dict) or "columns" not in data:
            return data
        data = dict(data)
        columns = data.pop("columns")
        if data.get("fields") or data.get("shape"):
            raise ValueError("a table declares columns and fields (or a shape): columns is the 0.2 word, so declare "
                             "fields or a shape only")
        if isinstance(columns, list):
            parsed = [TableColumn(name=c) if isinstance(c, str) else TableColumn.model_validate(c) for c in columns]
            data["fields"] = [c.as_field() for c in parsed]
            data["legacy_absence"] = {c.name: c.absence for c in parsed if _words(c.absence)}
        else:
            data["fields"] = columns
        _legacy("columns", "fields", "table")
        return data

    @model_validator(mode="after")
    def _shape(self) -> "TableDeclaration":
        if _words(self.shape) and self.fields:
            raise ValueError("a table names a shape and declares fields: its fields are said in one place")
        if _words(self.shape) and self.shape not in SHAPES:
            raise ValueError(f"a table names shape '{self.shape}', which is not registered")
        names = self.column_names()
        if not names:
            raise ValueError("a table declares no fields")
        twice = sorted({n for n in names if names.count(n) > 1})
        if twice:
            raise ValueError(f"a table declares column {', '.join(twice)} more than once")
        missing = [k for k in self.key_fields if k not in names]
        if missing:
            raise ValueError(f"a table's key_fields {', '.join(missing)} are not among its columns")
        nameless = [f.name for f in self.row_fields() if f.kind == "cell" and not _words(f.measure)]
        if nameless:
            raise ValueError(f"a table's cell column {', '.join(nameless)} names no measure: a cell's absence sentence "
                             "is its measure's, so say which measure it is the per-member value of")
        if self.max_rows < 1:
            raise ValueError(f"a table declares max_rows {self.max_rows}: a table shows at least one row")
        if self.max_rows > TABLE_MAX_ROWS:
            raise ValueError(f"a table declares max_rows {self.max_rows}: a table shows at most {TABLE_MAX_ROWS:,} "
                             "rows (owner's cap, 2026-11-02); every row is stored, so lower it or leave it out")
        lacking = [p for p in TRUNCATION_PLACEHOLDERS if p not in self.truncation]
        if _words(self.truncation) and lacking:
            raise ValueError(f"a table's truncation sentence '{self.truncation}' lacks {', '.join(lacking)}: it says "
                             "how many rows were shown of how many")
        if len(self.summary) != len(set(self.summary)) or any(not _words(s) for s in self.summary):
            raise ValueError("a table's summary names a measure twice, or an empty one")
        return self

    def row_fields(self) -> list[Field]:
        """A row's fields, in declared order: the inline fields, or the registered shape's, resolved."""
        if _words(self.shape):
            return [f for _, f in resolve_fields(self.shape)]
        return list(self.fields)

    def column_names(self) -> list[str]:
        return [f.name for f in self.row_fields()]

    def __eq__(self, other):
        # The kept 0.2 absence text is not part of what a table says: a table equals its own round trip.
        if isinstance(other, TableDeclaration):
            return self.model_dump() == other.model_dump()
        return super().__eq__(other)

    __hash__ = None

    @property
    def columns(self) -> list[LegacyColumn]:
        """DEPRECATED (0.3.1 compat for 0.2 readers): the row's fields as 0.2 columns. Use `row_fields()`.

        `type` is the 0.2 type name (string -> text, int -> integer, float -> number; `int`+`bytes` -> bytes,
        `float`+`seconds` -> duration; a string whose `valid_values` is a state set, or states, -> state with `states`
        filled; `date` and `datetime` both read `datetime`). `absence` is the text a 0.2 `columns` list declared, else
        "": in 0.3 a cell's absence sentence is its measure's, on `Declaration.absence`, which a table cannot see; use
        `Declaration.table_columns()` to have it filled in. `fields` is not compat: it is a list in 0.3 (a method in 0.2).
        """
        warnings.warn("TableDeclaration.columns is the 0.2 API, kept for readers not yet moved: use row_fields() "
                      "(or Declaration.table_columns() for the absence text)", LegacyApiWarning, stacklevel=2)
        return self._legacy_columns_view()

    def _legacy_columns_view(self, absence=None) -> list[LegacyColumn]:
        out = []
        for f in self.row_fields():
            states: tuple[str, ...] = ()
            ctype = _REVERSE_COLUMN_TYPES.get((f.type, f.unit), None)
            vv = f.valid_values
            if f.type == "string" and not f.unit and vv is not None:
                known = STATE_SETS[vv].states if isinstance(vv, str) and vv in STATE_SETS else \
                    tuple(vv) if isinstance(vv, list) and all(v in CELL_STATES for v in vv) else None
                if known is not None:
                    ctype, states = "state", known
            if ctype is None:   # a unit on a type 0.2 spelled differently: keep its unit, take the type's plain name
                ctype = _REVERSE_COLUMN_TYPES.get((f.type, ""), "text")
            text = self.legacy_absence.get(f.name, "")
            if not text and absence is not None and f.kind == "cell":
                text = absence
            out.append(LegacyColumn(name=f.name, type=ctype, unit=f.unit, absence=text, states=states,
                                    key=f.name in self.key_fields))
        return out

    def column(self, name: str) -> Field | None:
        return next((f for f in self.row_fields() if f.name == name), None)

    def as_dataset_field(self, name: str = "rows", label: str = "Rows") -> Field:
        """The table as §5 says it: a `dataset` field whose shape is the table's registered shape (BRIEF RS-W1-1 §2).
        Needs a registered shape; inline fields have no shape name to give."""
        if not _words(self.shape):
            raise ValueError("a table with inline fields is not a registered shape: register its fields "
                             "(`register_shape`) and name the shape")
        return Field(name=name, label=label, kind="dataset", shape=self.shape)

    def fields_in_order(self) -> list[str]:
        """The key, then the other fields, in declared order: a row's fields as a reader shows them."""
        names = self.column_names()
        return list(self.key_fields) + [n for n in names if n not in self.key_fields]

    def lacks(self) -> list[str]:
        """What a member- or field-scoped table still owes (Architect ruling, 2026-11-02): its key, its truncation, its
        order and its summary. [] when it owes nothing. (0.2 also asked an absence word of every non-key column; since
        0.3 a cell's sentence is its measure's, and a cell that names no measure is refused.)"""
        out = ["table.key_fields"] if not self.key_fields else []
        out += [f"table.{f}" for f in ("truncation", "order") if not _words(getattr(self, f))]
        out += ["table.summary"] if not self.summary else []
        return out

    def truncation_words(self, shown: int, total: int) -> str:
        """The shown slice's `lower_bound` rendering: the truncation sentence filled; "" when nothing was dropped."""
        return self.truncation.format(shown=shown, total=total) if total > shown and _words(self.truncation) else ""

    def extent(self) -> ExtentDeclaration | None:
        """The extent a table is (§5: "a table result's extent IS its table"): its fields, its cap, its order and
        truncation words, priced at about `TOKENS_PER_CELL` a cell, with the price of one row beside the whole so the
        compiler can quote a prefix. None until the table declares an order and a truncation."""
        if not (_words(self.order) and _words(self.truncation)):
            return None
        fields = self.fields_in_order()
        per_row = len(fields) * TOKENS_PER_CELL
        return ExtentDeclaration(name="rows", fields=fields, rows=self.max_rows, order=self.order,
                                 truncation=self.truncation, token_cost=self.max_rows * per_row,
                                 token_cost_per_row=per_row, citation="{analysis} · {scope} · as of {as_of}")


#: Each non-numeric kind -> the Declaration field that holds its block.
KIND_BLOCKS = {"finding": "finding", "proposal": "proposal", "list": "listing", "table": "table"}


class Declaration(_Strict):
    """What an analysis declares about its results (§1). `result_kind`, `measures` and `absence` are the minimum."""
    result_kind: str
    #: Required when the kind is `table` (§1: "none fits -> table and say so"): why none of the other seven fits.
    result_kind_note: str = ""
    #: Required for the numeric kinds; optional for finding, proposal, list and table, which are told by their block
    #: ("4 findings" is a count that is still welcome).
    measures: list[MeasureDeclaration] = _Default(default_factory=list)
    absence: AbsenceSentences
    extents: list[ExtentDeclaration] = _Default(default_factory=list)
    confidence: ConfidenceDeclaration | None = None
    #: The question ids this answers. None means not yet declared; [] declares that it answers none, which keeps it
    #: runnable and rendered and out of every chat answer (§3 step 1). For Resource Explorer's own analyses it is
    #: generated from the question catalogue (project owner, 2026-10-28), never written by hand.
    answers: list[str] | None = None
    #: False for an analysis that is registered and declared but has no runner yet (project owner, 2026-10-28:
    #: declare them, marked not built, so they read as "planned, not measured" rather than as nothing).
    built: bool = True
    scope: Literal["resource", "container", "member", "field"] | None = None
    #: Required when `result_kind` is graph or distribution.
    categories: CategoriesDeclaration | None = None
    #: One block per non-numeric kind, required when `result_kind` is that kind and refused on any other.
    finding: FindingDeclaration | None = None
    proposal: ProposalDeclaration | None = None
    #: The `list` kind's block (named so it does not shadow the builtin inside this class).
    listing: ListDeclaration | None = None
    table: TableDeclaration | None = None

    @field_validator("result_kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in RESULT_KINDS:
            raise ValueError(f"result_kind '{v}' is not one of the {len(RESULT_KINDS)} kinds "
                             f"({', '.join(RESULT_KINDS)}); if none fits, declare 'table' and say why in "
                             "result_kind_note")
        return v

    @field_validator("scope", mode="before")
    @classmethod
    def _scope(cls, v):
        if v is not None and v not in SCOPES:
            raise ValueError(f"scope '{v}' is not one of the levels ({', '.join(SCOPES)})")
        return v

    @model_validator(mode="after")
    def _whole(self) -> "Declaration":
        if self.result_kind == "table" and not _words(self.result_kind_note):
            raise ValueError("result_kind 'table' declares no result_kind_note: say why none of the other kinds "
                             "fits")
        if not self.measures and self.result_kind in MEASURED_KINDS:
            raise ValueError(f"declares no measures: a '{self.result_kind}' reports at least one, with its unit and "
                             "as-of")
        self._kind_blocks()
        if self.table is not None:
            self._table()
        names = [m.name for m in self.measures]
        twice = sorted({n for n in names if names.count(n) > 1})
        if twice:
            raise ValueError(f"measure {', '.join(twice)} is declared more than once")
        extents = [e.name for e in self.extents]
        twice = sorted({n for n in extents if extents.count(n) > 1})
        if twice:
            raise ValueError(f"extent {', '.join(twice)} is declared more than once")
        if self.answers is not None:
            blank = [a for a in self.answers if not _words(a)]
            if blank:
                raise ValueError("answers carries an empty question id")
        exact = [m.name for m in self.measures if m.uncertainty is not None and self.confidence_of(m)
                 and self.confidence_of(m).form == "measured"]
        if exact:
            raise ValueError(f"measure {', '.join(exact)} declares uncertainty and confidence 'measured': an exact read "
                             "has no spread, so declare the confidence that has one (estimated, inferred) or leave "
                             "uncertainty out")
        generated = [m.name for m in self.measures if m.annotation and self.confidence_of(m)
                     and self.confidence_of(m).form == "generated"]
        if generated:
            raise ValueError("confidence form 'generated' declares an annotation: a generated answer is not "
                             f"published, so it writes as nothing (measure {', '.join(generated)})")
        own = [m.confidence for m in self.measures if m.confidence is not None]
        if own:
            forms = [c.form for c in own] + ([self.confidence.form] if self.confidence and
                                              len(own) < len(self.measures) else [])
            weakest = max(forms, key=CONFIDENCE_STRENGTH.index)
            if self.confidence is None:
                if len(own) < len(self.measures):
                    raise ValueError("a measure declares its own confidence and the declaration none: the measures "
                                     "without one have no confidence to inherit")
                self.confidence = next(c for c in own if c.form == weakest)
            elif self.confidence.form != weakest:
                raise ValueError(f"confidence form '{self.confidence.form}' is not the weakest of its measures' "
                                 f"('{weakest}'): the declaration's confidence is its weakest link")
        return self

    def _kind_blocks(self) -> None:
        """The block each kind declares: required for its own kind, refused on another, so a declaration says what its
        kind means in words and carries nothing it does not use. Categories likewise for graph and distribution."""
        for kind, attr in KIND_BLOCKS.items():
            block = getattr(self, attr)
            if self.result_kind == kind and block is None:
                need = {"finding": "what_field (and where_field, if it is about a place)", "proposal": "candidate_field and decided_by",
                        "list": "item_fields, order and key_field", "table": "a shape (or fields) and key_fields"}[kind]
                raise ValueError(f"result_kind '{kind}' declares no {attr} block: say {need} so the headline, the "
                                 "publish table and Chat read it from the declaration")
            if self.result_kind != kind and block is not None:
                raise ValueError(f"declares a {attr} block and result_kind '{self.result_kind}': the block belongs "
                                 f"to result_kind '{kind}'")
        if self.result_kind in CATEGORY_KINDS and self.categories is None:
            raise ValueError(f"result_kind '{self.result_kind}' declares no categories: add categories with "
                             "exclusive true (one item in exactly one category) or false (an item may be in several), "
                             "and sums_to naming the result field that holds the stated total, if there is one")
        if self.result_kind not in CATEGORY_KINDS and self.categories is not None:
            raise ValueError(f"declares categories and result_kind '{self.result_kind}': categories belong to "
                             f"{' and '.join(CATEGORY_KINDS)}")

    def _table(self) -> None:
        """A table's rules that need the rest of the declaration (DESIGN-B1 §2-3; Architect ruling 2026-11-02).

        The gate is the declaration's SCOPE. A table at member or field scope is about the members of a resource and
        owes its key, truncation, order and summary (`TableDeclaration.lacks`). For
        one release a lack is REPORTED by `missing()`, never refused, so a pre-B1 declaration keeps loading until it
        converts (convert-as-touched). Once it owes nothing it is a table result (`is_table_result`): its extent is
        derived from the table, and an extent written beside a derived one is refused.

        A resource-scoped or unscoped table keeps bare columns and hand-written extents. Whatever the scope, a summary
        or a cell column's measure names a declared measure."""
        t = self.table
        declared = {m.name for m in self.measures}
        unknown = [s for s in t.summary if s not in declared]
        if unknown:
            raise ValueError(f"a table's summary names {', '.join(unknown)}, which is not a declared measure")
        refs = [f"{f.name} -> {f.measure}" for f in t.row_fields()
                if f.kind == "cell" and _words(f.measure) and f.measure not in declared]
        if refs:
            raise ValueError(f"a table cell column's measure names no declared measure ({', '.join(refs)})")
        if self.scope not in KEYED_SCOPES:
            return
        derived = t.extent()
        if derived is None:
            return
        if self.extents and self.extents != [derived]:
            raise ValueError("declares extents and result_kind 'table': a table's extent is its table, derived from "
                             "its fields, max_rows, order and truncation, so leave extents out")
        self.extents = [derived]

    def is_table_result(self) -> bool:
        """Is this a table result (B1): a member- or field-scoped table that owes nothing? Only a table result stores
        its rows, draws the table block, publishes its summary alone and quotes its stored rows."""
        return self.table is not None and self.scope in KEYED_SCOPES and not self.table.lacks()

    def table_columns(self) -> list[LegacyColumn]:
        """DEPRECATED (0.3.1 compat): the table's 0.2 columns with `absence` filled as far as 0.3 knows it: the text a
        0.2 `columns` list declared, else, for a `cell` column, this declaration's `not_measured` sentence (an empty
        cell is a value not measured), else "". Use `table.row_fields()` and `absence.sentence(...)`."""
        if self.table is None:
            return []
        warnings.warn("Declaration.table_columns() is a 0.2 compat view: use table.row_fields() and absence.sentence()",
                      LegacyApiWarning, stacklevel=2)
        return self.table._legacy_columns_view(absence=self.absence.not_measured)

    def confidence_of(self, measure: MeasureDeclaration) -> ConfidenceDeclaration | None:
        """A measure's confidence: its own, else the declaration's."""
        return measure.confidence or self.confidence

    def scope_of(self, measure: MeasureDeclaration) -> str | None:
        """A measure's scope: its own, else the declaration's (None when neither is declared)."""
        return measure.scope or self.scope

    def measure(self, name: str) -> MeasureDeclaration | None:
        return next((m for m in self.measures if m.name == name), None)

    def missing(self) -> list[str]:
        """The full-declaration fields this one does not declare yet, in `FULL_FIELDS` order, then, for a member- or
        field-scoped table, what it still owes ("table.key_fields", "table.truncation", "table.order",
        "table.summary"); [] when complete."""
        out = [f for f, absent in (("extents", not self.extents), ("confidence", self.confidence is None),
                                   ("answers", self.answers is None), ("scope", self.scope is None)) if absent]
        if self.table is not None and self.scope in KEYED_SCOPES:
            out += self.table.lacks()
        return out

    def is_complete(self) -> bool:
        return not self.missing()


MeasureDeclaration.model_rebuild()
Declaration.model_rebuild()


def refusal(exc: Exception) -> str:
    """A validation failure as one sentence per problem, without pydantic's framing ("1 validation error for ..."),
    naming where in the declaration each one is."""
    errors = getattr(exc, "errors", None)
    if not callable(errors):
        return str(exc)
    parts = []
    for e in errors():
        where = ".".join(str(p) for p in e.get("loc", ()))
        msg = str(e.get("msg", "")).removeprefix("Value error, ")
        if e.get("type") == "extra_forbidden":
            msg = "is not a declaration field"
        elif e.get("type") == "missing":
            msg = "is required"
        parts.append(f"{where} {msg}" if where else msg)
    return "; ".join(parts)
