# Scroll experiment: Mode 0

This 128×128 example moves an 8×8 character through a 192×192 tile map. The character can move within a centered 64×64 zone; crossing it moves the camera by one 8-pixel tile. The camera stops at all four map edges. A solid tile, an object, and another character block movement.

Build from the repository root with `python3 tools/build/build_examples.py scroll0`. Load `build/scroll0/scroll0.dsk` in a CPC emulator and run `RUN"SCROLL0"`. Use **O** west, **P** east, **Q** north, and **A** south. Movement is two pixels per update in either axis. From the starting position, north, south, and east lead to the three blockers; move west to go around them.

Press **T** once to enable the experimental playable hardware camera. It updates only the entering tile strip and moves the CRTC origin on camera steps; ordinary player movement and collision controls stay the same. Reload the disk to return to the full-redraw baseline. BluePixel CPC 6128 matches the baseline exactly at all four map edges. Measured horizontal camera steps now take two frames, but still jump one whole 8-pixel tile.

Press **S** instead of T to try the byte-step camera. It builds the next picture in the other half of video memory and switches at VSYNC. Each camera step moves **2 pixels** horizontally or vertically, while keeping the same 128×128 playfield and collision rules. At the four map edges its pixels match the full-redraw reference in BluePixel CPC 6128. The smaller steps take more time: consecutive westward camera changes were 7 frames apart in this emulator. Choose T for faster movement or S for smaller visual steps; reload the disk to change paths.

Before enabling T, **H** enters the isolated R13 probe. Press **H** again to restore R13=0 and resume play.

Press **J** for one east tile, **L** for one west tile, **K** for one row south, or **I** for one row north. The east/west probes fill the incoming column after active scanout. All probes pause game drawing; **H** restores the playable baseline. These probes passed in BluePixel CPC 6128.

The default camera uses a full tilemap redraw. The J/L/K/I probes remain isolated from movement; T and S enable alternative integrated camera paths. CPC 464 and physical hardware remain unverified. See [validation](../../docs/design/validation.md) and [design](../../docs/design/four-way-tile-scroll.md).
