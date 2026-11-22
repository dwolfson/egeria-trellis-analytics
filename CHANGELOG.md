# Changelog

## 0.5.0

The reader seam gains one read (TR-114). A new member of a runtime-checkable Protocol is a widening of the contract an
implementation must meet, so this is a minor release, not 0.4.x: a consumer pinned `>=0.4,<0.5` never sees it.

- **`OdsRead.filesystem_own_reads(slug, since="")`**: the runs in which Resource Explorer itself opened a file system's
  files after the walk (data-file profiles, narrative files, data-class matches), as `{step, surveyed_at, started_at}`.
  `fs_activity` uses it to count accesses at or after Resource Explorer's first read apart from a person's reads.

## 0.4.0

Declared shapes, the routine declaration, and the first renderer (BRIEF RS-W2-1b, library part; owner decisions D2, D4).
Additive: every 0.3.1 declaration loads unchanged, and the 0.3.1 compat API (`TableDeclaration.columns`,
`LegacyApiWarning`) is kept.

- **`Declaration.out`** (optional): what the result is, field by field: a registered shape's name, an inline `Shape`, or
  a list of `Field`s. When declared, each field a measure names (`value_field`, `as_of`, `basis.denominator_field`,
  `completeness_field`; the first part of a dotted path, `run.` excepted) must be a field of `out`. `out_fields()`,
  `out_field(name)`.
- **`trellis_analytics.routine`** (new): `RoutineDeclaration`, the routine-declaration schema pyegeria mirrors (D2):
  `name`, `kind` (producer | processor | routine | step), `description`, `version`, `source`, `family`, `tags`,
  `generic`, `binding_note`, `inputs` (role words `egeria_client:<Class>`, `reader:<name>`, `viewer`, `subject`),
  `params` (`ParamDeclaration`: name, type, default | required, category content | shape | performance, description),
  `constants`, `in` (a processor's input shape), `declaration` (results, including `out`), `pushdown`, `tile_safe`
  (`TileSafety`: safe, cap, reason), `admission` (resource_types, test_only), `bindings` (`Binding`: python |
  egeria_query | sql | step, target), `annotation_type`. `routine_declaration(manifest)` reads any manifest or pyegeria
  `AnalyticFunctionSpec` as one. `ReaderDeclaration`: a reader's reads, each a registered shape or a field type.
- **Field types:** `object` (a JSON object the shape does not describe further) and `map<string,list<T>>`.
- **`MeasureDeclaration.population`** (`viewer` | `repository` | empty) and **`Field.description`**, so pyegeria's mirrored
  declarations (W2-1a) load here unchanged.
- **Reader shapes** (`trellis_analytics.readers.shapes`): `CommitProof`, `CatalogueScopeEvent`, `NodeSet`,
  `NodeSetSchema`, and `READERS` for `ods` and `catalogue_scope`: the four reads `curation_coverage` makes. The other
  nine ODS reads are not declared yet (`READERS["ods"].undeclared(ODS_READS)` names them).
- **Every registry entry this package ships is declared:** `curation_coverage` (measure; out `CoverageResult`),
  `context_pack` (list; out `ContextPack`), `curation_coverage_tile` (measure). `manifests.ROUTINES` holds each as a
  `RoutineDeclaration`. `RoutineManifest.declaration` is now the library's `Declaration`, as on a step.
- **`CoverageResult`** gains two fields, `published_schemas` and `not_yet_schemas` (the tile's two numbers, which the
  measures name). Both are `None` when the result has no counts; `to_dict()` carries them.
- **`trellis_analytics.render.kpi_tile`** (new): the KPI tile rendered from a routine's declaration and its result,
  format `KPI`. Byte-identical to the 0.3.1 hand-built tile in every state (tested against a frozen copy of the 0.3.1
  builder).
- The registered function `curation_coverage_tile` now runs `portal.curation_coverage_kpi`. The report spec is
  unchanged. Through pyegeria's executor, an absent tile now carries the declared absence sentence instead of the
  generic one.
- **Deprecated:** calling `trellis_analytics.portal.curation_coverage_tile` by its Python name warns `LegacyApiWarning`
  and returns the same tile. It will be removed in 0.5. Call `curation_coverage_kpi`.

## 0.3.1

Compatibility fix: 0.3.0 removed the 0.2 table API its README said still loaded.

- `TableDeclaration.columns` returns, read-only and deprecated (`LegacyApiWarning`): 0.2-shaped columns (`name`, `type`,
  `unit`, `absence`, `states`, `key`) derived from `row_fields()`. Column types map back to the 0.2 names.
- A 0.2 `columns` list's per-column `absence` text is kept and read back as written (0.3.0 dropped it). In a 0.3 table it is
  `""`; `Declaration.table_columns()` fills a cell column's with the declaration's `not_measured` sentence.
- Word change: a state column's `measured_nothing` reads `nothing_found` (the 0.3 word).
- Not restored: `fields()` as a method (`fields` is the 0.3 list; use `fields_in_order()`), and `Field.absence` / `Field.states`.

## 0.3.0

See the README, "The vocabulary (0.3)".
