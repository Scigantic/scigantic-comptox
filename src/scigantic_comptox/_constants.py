"""Shared constants: where the mirror lives, and the live CCTE API base."""

BUCKET = "scigantic-comptox"
REGION = "us-east-1"

# EPA's Computational Toxicology and Exposure (CCTE) REST API. Requires an
# individual API key (see ctx_client.py) -- EPA's own docs describe it as
# "an individual API key" that "uniquely identifies the user", and issuance
# is manually gated through ccte_api@epa.gov rather than self-serve. EPA's
# own reference client (github.com/USEPA/ctx-python) never embeds a key and
# always requires the caller to supply their own; this package does the
# same, deliberately, rather than proxying a shared Scigantic-side key.
CTX_API_BASE = "https://api-ccte.epa.gov"
CTX_API_KEY_ENV = "COMPTOX_API_KEY"
CTX_API_INFO_URL = "https://www.epa.gov/comptox-tools/computational-toxicology-and-exposure-apis-about"
CTX_API_KEY_CONTACT = "ccte_api@epa.gov"
