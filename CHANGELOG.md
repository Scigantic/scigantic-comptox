# Changelog

## 0.2.0

Real feedback from a separate ML pipeline evaluating CompTox as a
transfer-learning signal surfaced three gaps that traced to one root
cause: the mirror shipped EPA's fact table (bioactivity results) but none
of the small reference data EPA publishes alongside it. Rather than patch
in fields one at a time, this mirrors the whole small bundle at once.

- `assay_annotations()`: per-assay-endpoint design and target metadata
  (1,647 rows), including `intended_target_family` -- lets you filter to
  a target family (e.g. cytochrome P450) instead of string-matching on
  assay names.
- `assay_target_mappings()`: assay-to-gene mapping in long form (2,187
  rows), with real Entrez gene ids and official gene symbols. Distinct
  from `assay_annotations()`, whose target columns are broad categories,
  not gene-level identifiers.
- `cytotox()`: per-chemical cytotoxicity burst summary (10,487 rows) --
  lets a caller check whether a hit call sits near a chemical's cytotoxic
  concentration, a well-known ToxCast confound.
- `analytical_qc()`: per-chemical/per-sample QC pass/caution flags plus a
  few OPERA-predicted physicochemical properties (42,891 rows).
- `p_ac50`/`p_bmd`: computed log-potency columns on `bioactivity()`, the
  same shape as scigantic-chembl's `pchembl_value` / scigantic-bindingdb's
  `p_affinity`. Computed only where `conc_unit` is verified `'uM'`
  (98.8% of rows) -- a genuine 0.09% of rows carry `'mg/l'` instead (a
  mass-based unit needing a molecular weight this table doesn't have to
  convert correctly), and applying the uM-based transform there would
  silently produce a wrong potency value, not just a missing one.

All four reference tables together add under 3MB to the mirror.

## 0.1.1

Real perf and usability fix, found by stress-testing 0.1.0 against a
realistic batch workload (pulling bioactivity profiles for 500 chemicals).

- `bioactivity_many()`/`pubchem_bridge_many()`: batched lookups for many
  chemicals in one query. Looping `bioactivity(dtxsid=...)` per id is the
  natural way to write a batch pass, but it's slow here: the mirror isn't
  sorted or partitioned by chemical id, so each individual call pays close
  to a full scan of the table. Measured on the real mirror: 50 chemicals
  looped took 61.9s (1.24s/call) vs 4.8s batched -- a 13x difference that
  grows with batch size. Use these for anything beyond a handful of
  lookups.
- `query()`'s raw SQL layer now understands `dtxsid` on the `bioactivity`
  view, not just the raw `dsstox_substance_id` column name. `bioactivity()`'s
  `dtxsid=` parameter always filtered on the real column correctly, but
  someone writing their own SQL through `query()`/`connect()` had no way to
  know that without reading the source -- `pubchem_bridge`'s own source
  column is already natively named `dtxsid`, so this makes the two views
  consistent.

## 0.1.0

Initial release.

- `bioactivity()`/`bioactivity_raw()`: query the ToxCast `mc5-6_winning_model_fits`
  summary tier from `s3://scigantic-comptox` (v4.3, 3,527,285 rows). The
  normalized `bioactivity()` fixes two real data-quality issues in EPA's raw
  export: the literal string `"NA"` used in place of real `NULL`s in several
  identifier columns, and several genuinely numeric columns (`ac50`, `bmd`,
  `top`, and others) shipped as text.
- `pubchem_bridge()`: EPA's own per-assay-endpoint PubChem CID cross-reference,
  consolidated into one table (3,331,046 rows).
- `chemical_detail()`/`hazard_toxval()`/`exposure_httk()`: a thin live wrapper
  over EPA's CCTE REST API (Chemical/Hazard/Exposure), requiring the caller's
  own API key, never a shared/embedded one.
- `releases()`/`latest()`: manifest-driven, matching scigantic-chembl/
  scigantic-bindingdb's mechanism. DSSTox bulk chemical structures are not
  yet mirrored (`structures: False`); a future release can add them without
  a breaking change.
- Opt-in local caching for the mirror half (`enable_cache()`), default-on
  caching with a 30-day TTL for the live REST half (`ctx_cache`) -- matching
  the established convention across the family (opt-in for an unlimited
  public mirror, default-on for a live rate-limited-ish API).
