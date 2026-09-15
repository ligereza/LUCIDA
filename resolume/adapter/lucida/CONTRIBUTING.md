# Contributing to LUCIDA

## Technical ASCII boundary

Technical code and structured data use strict ASCII and English identifiers.
This applies to:

- identifiers, module names, imports, filenames and test names;
- contract keys, event fields, log fields and parseable messages;
- JSON schemas, fixtures and replay data.

Human-facing documentation may use Spanish or other languages. Keep that
content in documentation files and do not put Unicode into technical fields.
Human-readable notes may be localized only when they are outside the technical
contract boundary.

The offline guard scans Python and JSON files in the LUCIDA layer, the reused VJ
adapter, and their tests. Run it with:

```text
python -m pytest -q tests/lucida/test_ascii_guard.py
```

The full suite remains the required check before committing:

```text
python -m pytest -q
```
