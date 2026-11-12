# Mode 1 PNG import

## Goal

Let a game using `mode1-192x192.json` import byte-aligned sprites from PNG
through the existing asset pipeline, while preserving the output of Mode 0
projects that omit the new `mode` field.

## Contract

- `assets/assets.json` accepts `"mode": 0` or `"mode": 1`; omitted means Mode 0.
- Mode 0 has two pixels per byte, needs sprite widths divisible by two, and
  uses sixteen firmware palette values. Mode 1 has four pixels per byte, needs
  widths divisible by four, and uses four firmware palette values.
- The importer passes the selected mode to `img2cpc`, checks the aggregate
  expected byte count for all tiles in each image, then slices the output into
  equal tiles. It writes a palette-size constant to the generated include and
  tile dimensions as comments in the generated assembly. Asset pipeline hashes include the configuration bytes, so changing
  `mode` makes existing generated files stale.
- The build checks the asset mode against the selected video profile before
  conversion. A Mode 1 project cannot silently link Mode 0 sprite bytes.
- `mode` must be a JSON integer; booleans and floats are rejected.

## Files

- Modify `tools/build/import_assets.py` for mode validation, palette size,
  `img2cpc -m`, byte count, and generated comments.
- Modify `tools/build/build_examples.py` to compare the asset and profile modes.
- Modify `tests/test_import_assets.py` for default Mode 0, Mode 1 validation,
  converter invocation, multiple tile slicing, short/long output rejection,
  palette output, pipeline state, and build-stage mismatch rejection.
- Update `README.md` with a support summary and `docs/reference/sprites.md`
  with a Mode 1 asset example.

## Verification

Focused unit tests use a fake converter to check command and output contracts.
A real `img2cpc` conversion of a four-colour 4×8 PNG produced eight sprite
bytes and a four-entry palette. A temporary Mode 1 program using that PNG,
transparency, and the 192×192 profile built into BIN, CDT, and DSK. The
temporary program's source was removed after the build.
The real Mode 0 `platformer` assets were reconverted in a temporary copy;
`assets.s`, `assets.inc`, and `pipeline.json` matched the checked-in files
byte for byte.

## Boundary

The importer produces CPC Mode 1 bytes. It does not decode Spectrum screen
memory or attribute colours. Built-in text and tile renderers remain Mode 0.
