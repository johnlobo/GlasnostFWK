# Mode 1 sprite support

## Goal

Make the existing eight-byte sprite descriptor and public drawing calls work
with the 192×192 Mode 1 profile. Coordinates and widths remain byte based:
one Mode 1 screen byte holds four pixels, so a sprite starts on a four-pixel
boundary. Clipping, capture, and restore retain their current contracts.

## Design

- The opaque draw, capture, restore, and clipping paths already copy bytes and
  use the active video width and height. They remain shared between modes.
- The project configuration accepts transparent pens 0–3 in Mode 1 and emits
  a 256-byte mask table in generated source. `fwk_project_init` copies the
  table to `0x0100` before masked drawing. A mask preserves both bits of each
  pixel whose source pen matches the configured transparent pen.
- Masked drawing composes `(background & mask) | (source & ~mask)` using that
  table. Its direct drawing routine advances screen rows by the active width
  in bytes when moving from raster 7 to raster 0.
- Recolouring accepts pens 0–3 in Mode 1. CPCtelera supplies repeated old and
  new pen patterns. A source byte XOR old pattern exposes mismatched bits;
  rotating that byte four bits and ORing identifies both bits of every
  mismatched pixel. The complement selects both bits of matching pixels,
  which are replaced using the old/new pattern difference.
- The masked recolour path recolours the source byte before looking up its
  transparency mask. Recolouring to the transparent pen hides a pixel; changing
  a transparent pen to an opaque one reveals it.
- Mode 0 keeps its existing mask and recolour logic. The video mode is carried
  into generated project configuration so the assembler selects the right
  routine and the generator creates the right mask table.

## Files and checks

- Modify `tools/build/project_config.py` to validate the Mode 1 pen range,
  create the Mode 1 mask table, and expose the video mode in generated project
  configuration.
- Modify `framework/src/video/sprite.s` to select the CPCtelera pattern
  converter and recolour mask for the active mode. Keep the byte-based drawing,
  capture, restore, and clipping paths shared.
- Modify `framework/src/video/transparency.s` to use the active video width
  for its raster wrap, including callers outside the sprite module.
- Modify `tools/build/build_examples.py` to reject the built-in Mode 0 text
  and tile renderers when a Mode 1 profile is selected.
- Modify `tests/test_project_config.py` and `tests/test_sprite_masked.py` for
  Mode 1 pen validation, all-byte mask properties, fixed CPC Mode 1 vectors,
  recolour results, and transparency after recolouring.
- Update `README.md`, `docs/reference/sprites.md`, and
  `docs/reference/architecture-and-api.md` to state the Mode 1 contract and
  the remaining asset/text/tile limits.

## Verification

- Unit tests check all 256 Mode 1 mask entries against four decoded pixels,
  fixed `0x35` golden vectors for pens 0–3, pen validation, and the
  recolour/transparency order.
- Build the existing Mode 0 `spritemask` program and compare its `sprite.rel`
  object byte for byte against the previous source assembled with the same
  generated configuration. Build a temporary Mode 1 probe with configured
  transparency and calls to all sprite entry points. Remove the probe after
  the build; it is not a new catalog program.
- Check generated video geometry and run the focused host tests. Emulator
  behaviour needs a separate smoke run when an emulator is available.

## Boundaries

The PNG asset importer now supports Mode 1 with `"mode": 1` and four firmware
colours. Built-in text still assumes Mode 0. The tile renderers copy packed bytes and
are allowed with Mode 1 since the follow-up that lifted the build gate
(`examples/mode1` draws opaque and masked strips, checked in the emulator). This change
provides byte-aligned Mode 1 sprite drawing and PNG conversion. Sub-byte X
placement and conversion of Spectrum pixel/attribute data are separate work.
