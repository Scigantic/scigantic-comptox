# Changelog

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
