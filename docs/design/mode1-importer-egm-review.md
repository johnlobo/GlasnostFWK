# EGM Goldfish review: Mode 1 importer

The fresh Codebase Details reviewer checked the importer design against the
implementation and tests. Its findings and resolutions:

- The design promised an asset example in the README, where there was only a
  support summary. The design now points to the JSON example in the sprite
  reference.
- The importer validates aggregate output length and splits the byte stream
  into equal tiles. The design now says this exactly. Tests cover two tiles
  and reject short and long converter output.
- Mode 0 compatibility needed an active conversion comparison. A temporary
  copy of the `platformer` assets was reconverted with the real `img2cpc`;
  all three generated files matched byte for byte.
- The design described tile dimensions as generated symbols. It now states
  that tile dimensions are comments, while palette size is a constant.
- Tests now check the four emitted palette bytes, the include size constant,
  and that a build-stage mode mismatch fails before conversion starts.

No runtime CPC display check was possible; the local emulator is unavailable.
