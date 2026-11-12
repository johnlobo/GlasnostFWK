# EGM Goldfish review: Mode 1 sprites

The fresh Codebase Details reviewer read the Mode 1 design and the current
sprite, transparency, project configuration, and build code. It reported three
major gaps and one minor gap in the design document.

- The design did not name the files or the verification steps precisely. The
  file list and temporary probe procedure are now explicit.
- The mask test repeated the generator's bit formula. Fixed CPC Mode 1 byte
  vectors and composition results now supplement the exhaustive test.
- Compiling Mode 0 did not prove its recolour bytes stayed the same. The old
  and new `sprite.rel` objects were assembled with the same configuration and
  compared byte for byte; they match.
- The design said the table was emitted at `0x0100`. It now specifies that
  `fwk_project_init` copies the generated table there before masked drawing.

The reviewer found no Mode 1 bit-pair or 48-byte row-stride discrepancy in the
inspected code. Runtime display behavior remains unverified without an emulator
or CPC hardware.
