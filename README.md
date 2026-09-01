<h1 align="center">scigantic-comptox</h1>

<p align="center">
    <a href="https://github.com/Scigantic/scigantic-comptox/actions/workflows/ci.yml">
        <img alt="CI" src="https://github.com/Scigantic/scigantic-comptox/actions/workflows/ci.yml/badge.svg" /></a>
    <a href="https://pypi.org/project/scigantic-comptox/">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/scigantic-comptox" /></a>
    <a href="https://pypi.org/project/scigantic-comptox/">
        <img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/scigantic-comptox" /></a>
    <a href="https://github.com/Scigantic/scigantic-comptox/blob/main/LICENSE">
        <img alt="License" src="https://img.shields.io/github/license/Scigantic/scigantic-comptox" /></a>
</p>

Query EPA's [CompTox Chemicals Dashboard](https://comptox.epa.gov/dashboard/) from Python. Two halves, and only one of them needs anything from you:

- **ToxCast bioactivity**, from a public S3 mirror over DuckDB. No API key, no download, no local database.
- **Live Chemical/Hazard/Exposure lookups**, over EPA's own CCTE REST API. Optional, and requires your own EPA API key.

```python
import scigantic_comptox as comptox

df = comptox.bioactivity(dtxsid="DTXSID7020182", hitc=1.0)
```

That query runs against `s3://scigantic-comptox` over DuckDB's httpfs extension.

## Installation

```console
$ pip install scigantic-comptox
```

## What's in the bioactivity mirror

Every row is the winning dose-response model plus hit-call for one (chemical, ToxCast assay endpoint) pair, from EPA's `invitrodb` v4.3 `mc5-6_winning_model_fits` summary tier: AC50, potency, top, confidence bounds, and `hitc`/`hitcall` (active/inactive/ambiguous). This is the same level of detail as PubChem's own `concise` BioAssay tables, deliberately not the raw well-level plate reads or the full set of *losing* candidate curve models EPA also publishes (`mc4_all_model_fits`) -- that table is what makes EPA's own "summary" download 7GB instead of the ~600MB actually mirrored here; almost nobody needs the losing models, they need the winner.

```python
comptox.bioactivity(aeid=1114, limit=5)
```

EPA's export uses the literal string `"NA"` for missing values in several columns (including `dsstox_substance_id`), not a real SQL `NULL` -- filtering with `IS NOT NULL` silently misses these. `bioactivity()` normalizes this (`NULLIF(..., 'NA')`) so a real `NULL` check works as expected; it also casts columns EPA ships as text purely because of those `"NA"` strings (`ac50`, `bmd`, `top`, and others) to real `DOUBLE`s. Use `bioactivity_raw()` if you want EPA's exact upstream types instead.

`p_ac50`/`p_bmd` are computed log-potency columns, the same shape as [scigantic-chembl](https://github.com/Scigantic/scigantic-chembl)'s `pchembl_value` and [scigantic-bindingdb](https://github.com/Scigantic/scigantic-bindingdb)'s `p_affinity`: `6 - log10(value_in_uM)`, higher meaning more potent. Computed only where `conc_unit` is verified `'uM'` (98.8% of rows) -- a real 0.09% carry `'mg/l'` instead, a mass-based unit this table can't convert correctly without a molecular weight, so those stay `NULL` rather than getting a silently wrong value.

### Batch lookups

The mirror isn't sorted or partitioned by chemical id, so `bioactivity(dtxsid=...)` pays close to a full scan of the table on every call. Fine for one lookup, slow for a batch -- use `bioactivity_many()` instead:

```python
comptox.bioactivity_many(["DTXSID7020182", "DTXSID2021868", "DTXSID3021805"])
```

Measured on the real mirror: 50 chemicals looped through `bioactivity()` took 61.9s; the same 50 as one `bioactivity_many()` call took 4.8s -- 13x faster, and the gap grows with batch size.

## PubChem cross-reference

EPA publishes a per-assay-endpoint PubChem CID cross-reference alongside each `invitrodb` release. This wraps the consolidated version of that file:

```python
comptox.pubchem_bridge(dtxsid="DTXSID7020182")
comptox.pubchem_bridge_many(["DTXSID7020182", "DTXSID2021868"])  # same batching win as above
```

Pairs naturally with [scigantic-pubchem](https://github.com/Scigantic/scigantic-pubchem)'s own BioAssay/gene/protein coverage.

## Reference tables

EPA publishes four small reference files alongside the bioactivity fact table -- target/design metadata, gene mapping, cytotoxicity context, and QC flags. All four are mirrored here too, under 3MB combined:

```python
comptox.assay_annotations(intended_target_family="cyp")   # filter assays by target family, not by string-matching assay names
comptox.assay_target_mappings(official_symbol="CYP2D6")   # real Entrez gene ids and gene symbols per assay
comptox.cytotox(dtxsid="DTXSID7020182")                    # is this chemical's hit call near its cytotoxic concentration?
comptox.analytical_qc(dtxsid="DTXSID7020182")               # sample QC pass/caution, plus molecular weight/logKow/vapor pressure
```

## Writing your own SQL

`comptox.query("SELECT ...")` and `comptox.connect()` run against the same `bioactivity`/`pubchem_bridge` views the functions above use, including the `"NA"`-normalization. `dtxsid` works directly in your own SQL too, not just as a Python parameter name:

```python
comptox.query("SELECT dtxsid, aeid, hitc FROM bioactivity WHERE dtxsid = 'DTXSID7020182'")
```

## What's not mirrored (yet)

DSSTox bulk chemical structures aren't mirrored -- EPA's bulk distribution for that turned out to be a large, unstructured institutional drive rather than a clean single file. `comptox.releases()` reports this plainly (`structures: False`) rather than silently missing the data. For now, chemical structure lookup by DTXSID goes through the live REST half below, the same place EPA's own client gets it from.

## The live REST half: bring your own EPA API key

EPA's CCTE API needs one, and deliberately doesn't hand out a shared one: their own docs describe it as "an individual API key" that "uniquely identifies the user," issued by emailing `ccte_api@epa.gov` rather than self-serve signup. EPA's own reference client, [`ctx-python`](https://github.com/USEPA/ctx-python), never embeds a key either. This package follows the same rule -- no key ships with it, and none is proxied on your behalf.

```console
$ export COMPTOX_API_KEY=your-key-here
```

```python
comptox.chemical_detail("DTXSID7020182")
comptox.hazard_toxval("DTXSID7020182")
comptox.exposure_httk("DTXSID7020182")
```

Calling any of these without a key raises `MissingApiKeyError` with a link to how to get one, not a bare 401. Requests are retried with backoff on 429/5xx, and responses are cached for 30 days by default (the opposite default from the mirror half's caching, see below) -- EPA's API has no documented rate limit, but it's still a live government service, not an unlimited public mirror, so repeatedly re-fetching the same lookup in a loop is worth avoiding by default.

Endpoint coverage here is intentionally a starting set (one real, verified path per microservice), not a full reimplementation of `ctx-python` -- that package already covers Chemical/Exposure/Hazard comprehensively. This package's actual differentiator is the bioactivity mirror above, which `ctx-python` doesn't cover at all.

## Working offline (mirror half)

Off by default, since zero setup is the whole point of the mirror:

```python
comptox.enable_cache()
df = comptox.pubchem_bridge()  # downloads the file once, then reads from disk
```

Downloads to `~/.cache/scigantic-comptox` (override with `enable_cache(cache_dir=...)` or the `SCIGANTIC_COMPTOX_CACHE` environment variable). Concurrent callers racing the first download of the same file wait for it rather than each downloading their own copy.

`connect()`, `query()`, and `bioactivity()` don't participate in this (registering the underlying views eagerly would mean the first call for any release downloads the full ~600MB regardless of what the query actually touches); use `comptox.cache_resolve("v4_3/derived/pubchem_bridge.parquet")` to cache a specific file yourself.

The live REST half has its own separate cache, ON by default (`comptox.disable_ctx_cache()` to turn it off) -- see above for why the two halves use opposite defaults.

## What's mirrored

```python
comptox.releases()
```

| release | bioactivity | pubchem bridge | reference tables | structures |
|---|---|---|---|---|
| v4_3 | yes | yes | yes | no |

This table isn't hardcoded. `releases()` reads a small manifest published alongside each mirror run.

## Command line

```console
$ scigantic-comptox info
$ scigantic-comptox query "SELECT count(*) FROM bioactivity" --release v4_3
```

## License

MIT-0. See [LICENSE](LICENSE). This covers the code in this package only.

## Data license

EPA's `invitrodb` v4.3 (ToxCast bioactivity data) is [CC0](https://creativecommons.org/publicdomain/zero/1.0/) -- public domain, no attribution or share-alike terms to track. A courtesy citation is appreciated, not required: Filer, D.L. et al. (2017), *tcpl: the ToxCast pipeline for high-throughput screening data*, Bioinformatics, [doi:10.1093/bioinformatics/btw680](https://doi.org/10.1093/bioinformatics/btw680).
