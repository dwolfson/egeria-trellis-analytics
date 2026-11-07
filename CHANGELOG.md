# Changelog

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
