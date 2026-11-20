# Four-way tile scrolling on classic Amstrad CPC

* **Author:** johnlobo
* **Status:** Proposed
* **Date:** 2026-11-12

## Overview

This design defines a first scrolling experiment for classic CPC 464 and CPC 6128 machines. A playable character will walk through a map in four directions. The camera will follow only after the character leaves a central movement zone, and it will stop at the map edges. The first experiment uses a 128×128-pixel visible playfield in Mode 0 and Mode 1. It tests CRTC display-start changes and newly exposed map strips against the pixel, memory-write, sprite, and timing checks below.

The prototype size is a test setting, not a limit for later games. Pixel-level scrolling is a later study that will use the measured results of this first stage.

## The Problem

GlasnostFWK can render a tilemap from a camera position expressed in whole tiles, but its example changes that position only once and then stops. It does not demonstrate a character moving across a larger map, reaching all four edges, or staying still when blocked by a solid tile, object, or character. The current renderer redraws the whole viewport when the camera changes; its measured cost on a small viewport does not show that a larger scrolling playfield can update at a playable rate.

The video system also assumes that the displayed image starts at a fixed address. A CRTC change without corresponding address handling would leave tile, sprite, text, clear, and background-capture operations writing to the wrong physical locations. A smaller fixed-origin display reads fewer bytes, but the union of all scrolling origins determines which addresses are available for other uses. The prototype must establish horizontal and vertical CRTC behavior and safe edge filling before the framework exposes a general scrolling API.

## Goals

1. Build a repeatable 128×128 Mode 0 experiment and a 128×128 Mode 1 experiment. Both modes must pass on CPC 464 and CPC 6128 emulator configurations; observations on available physical machines are recorded separately. Use an 8×8-pixel tile fixture with enough map area to reach all four camera limits.
2. Demonstrate a character moving in all four directions. Horizontal movement is one video byte per update; vertical movement is two scanlines in Mode 0 and four in Mode 1. The default centered movement zone is 50% of the playable width and height, with independently adjustable axis sizes.
3. Apply tile, object, and character collision decisions before updating the camera. A blocked move leaves the character and camera unchanged. At a map edge the camera stops while the character can move through the rest of the visible playfield until its own boundary or an obstacle blocks it.
4. Prove or reject hardware scrolling at whole-tile steps by checking observed CRTC state, displayed pixels, the full overlapping interior address set or an equivalent write trace, newly exposed map strips, sprite restoration, and both directions on each axis. Record elapsed cycles or frames, tearing, stale strips, and sprite remnants at every camera step.
5. Preserve the behavior and binary contracts of existing video profiles, tile renderers, sprites, and examples. Any scrolling path must be opt-in until its address mapping and hardware behavior are validated.
6. Use the measurements to decide whether to extract a small framework video-origin primitive and to define the separate pixel-scroll study. Do not present unmeasured support for other resolutions as complete.

## Non-Goals

* Pixel-level or sub-byte horizontal scrolling in this first stage.
* CPC Plus ASIC features or a design that depends on them.
* A general collision engine for every game object and character.
* Unlimited map dimensions, automatic map streaming, or changes to existing descriptor layouts in place.
* A claim that every current Mode 0 or Mode 1 profile can hardware-scroll without a separate validation.
* Production implementation during this document-drafting workflow.

## Open Questions

* What horizontal and vertical display-start steps actually work on the CPC 464 and 6128 CRTC variants and in the selected emulators? The local CPCTelera offset documentation and CPC screen-address notes describe horizontal granularity differently; the experiment must settle it with visible output.
* Can a new row or column be prepared without overwriting bytes still visible in the current frame? A smaller CRTC display does not create a separate memory pitch or an automatically safe hidden strip.
* Does a tile drawing primitive remain valid at every shifted origin and wrap point, or does the scroll path need its own per-scanline address resolver?
* Can the complete collision, edge-fill, CRTC-update, sprite-restoration, and drawing step finish within one 50 Hz frame (about 79,872 Z80 T-states)? This is the first-stage performance gate; a slower path remains a measured feasibility result, not a pass.

## Critical User Journeys (CUJs)

### CUJ 1: Walk through the map

* **Given:** A 128×128 visible playfield, a provisional 192×192 map with 8×8 tiles, a character initially near the middle, and Mode 0 or Mode 1 selected.
* **When:** The player holds a direction until the character crosses the central movement-zone boundary.
* **Then:** Collision and camera-origin checks pass before the proposed world position and camera are committed together. The camera moves by whole tiles only after the boundary is crossed. The character returns to the central zone when the camera can advance; after an edge clamp it may leave that zone until its own boundary. The test records world and screen positions and the camera tile after each step.

### CUJ 2: Reach an edge or obstacle

* **Given:** The character can approach each of the four map edges and at least one solid tile, object, and other character blocks a route.
* **When:** The player continues moving in a blocked direction.
* **Then:** A collision blocks the proposed movement before the camera changes. At a map edge, the camera stays at its limit while the character can continue toward its own boundary if the path is clear. No old sprite image or captured background is left behind.

### CUJ 3: Prove the hardware path

* **Given:** An instrumented 128×128 profile and a repeatable input path through every camera direction and reversal.
* **When:** A whole-tile camera step is requested.
* **Then:** The observed CRTC start or effective display address changes, the overlapping interior remains unchanged except for listed sprite/strip writes, the displayed image moves as predicted, and the newly exposed strip shows the correct tiles. A failed stage reports its own code and timing instead of ending as an unexplained timeout.

## Technical Plan (Architecture)

The plan separates gameplay position, camera policy, and physical display origin. This keeps collision rules out of the video system and allows the existing renderer to provide a baseline before any CRTC path is exposed.

```text
input -> proposed world move -> tile/object/character collision
                                      |
                                      v
                         proposed camera and map clamp
                                      |
                                      v
                         physical-origin validation
                                      |
                                      v
                   atomic world/camera/origin commit
                                      |
                  +-------------------+-------------------+
                  |                                       |
                  v                                       v
       existing full-view renderer              hardware-scroll experiment
       (behavior/timing baseline)               (edge strip, CRTC, sprite)
```

### 1. Establish the gameplay baseline

Use 8×8-pixel tiles so the 128×128 view contains 16×16 tiles. A 192×192 map contains 24×24 tiles and allows camera positions 0–8 on each axis: nine positions and eight tile steps of travel. Use the renderer's existing camera fields and full-view call to demonstrate the movement zone, four directions, four edge clamps, and collision-first order. Keep this camera-follow policy inside the example while its behavior is still being tested. Measure the redraw time with the same map and sprite content used later by the hardware path.

The character center is the camera anchor. Within a 128×128 playfield, the initial central zone is `32 <= x < 96` and `32 <= y < 96` in screen pixels. On a crossed threshold, advance the camera by enough whole tiles to return the anchor inside the zone, then clamp the camera to the map. Derive the character's screen position from the accepted world position and clamped camera. Use wider intermediate arithmetic when adding the sprite dimensions or calculating a clamp so 8-bit values never wrap. At a blocked movement, keep both positions and the camera unchanged. A large jump or teleport is outside the playable example but should be handled by the camera calculation rather than assumed to be one tile.

The shared test fixture uses world-pixel coordinates with an 8×8 opaque player sprite whose top-left starts at `(92,92)`. The starting camera is tile `(4,4)`, so the screen anchor is `(64,64)`. The map is otherwise passable except for a solid tile at tile `(12,8)` (pixel rectangle `[96,104)×[64,72)`), a blocking object at `[96,112)×[128,136)`, and another character at `[128,136)×[96,104)`. A proposed move tests the complete player rectangle against all occupied solid tiles and the two blocking rectangles. Any player extent outside `[0,192)×[0,192)` is blocked. One accepted key update per 50 Hz frame moves 2 pixels horizontally or vertically in Mode 0 and 4 in Mode 1, following the agreed byte-width horizontal rule; `O/P/Q/A` mean west/east/north/south. Ignore an update with zero or multiple directions, so every scripted command is one cardinal move. Each example keeps separate horizontal and vertical zone constants. From the start, a straight north approach stops at player top-left `y=72`, a straight south approach at `y=120`, and a straight east approach at `x=120` in either mode; the next step overlaps the respective blocker. Detours around those obstacles must reach player top-left `0` or `184` at each world edge, with camera tile `0` or `8` on the approached axis. Tests compare exact world/screen/camera states before and after every blocked step and edge rather than relying on a visual impression.

### 2. Make two isolated display experiments

Create separate 128×128 scrolling profiles for Mode 0 and Mode 1; do not alter the current standard or 192×192 profiles. The generated address model already accepts 64 video bytes per line for Mode 0 and 32 for Mode 1, using 8 KiB and 4 KiB of the 16 KiB video window. This is only fixed-origin validation. The hardware experiment must enumerate every reachable CRTC origin and the physical bytes read for all 128 lines, including map-edge positions, reverse movement, and wrap points. Reserve the union of those addresses before using remaining RAM for map data, tile graphics, stack, or code.

Extend the existing `tools/build/video_model.py` with CRTC-origin inputs rather than introducing a second address model. First run a bounded, sprite-free pattern probe over candidate origins to determine the actual horizontal step, row advance, and wrap; the probe does not claim a usable scroll path. Then compare observations with the extended model. For each confirmed candidate camera step, identify the entering tile row or column and the physical addresses that must be filled. Check whether those addresses are still displayed before changing the CRTC start. The CRTC's width setting also sets the row advance, so a new right-edge column may overlap a previous row's visible bytes. If no safe update order or buffer layout exists within the frame budget, record that result and stop the hardware branch instead of writing over visible data. Do not assume that unused bytes in the fixed-origin memory report form a usable margin.

### 3. Keep physical video addresses coherent

The current `fwk_video_get_ptr` uses a generated fixed line table. The hardware experiment must map a screen pixel or video-byte location to the physical address for the current display origin. Check every scanline of a tile at that origin, not just its first byte, because aligned tile routines may cross a CRTC wrap. The same mapping is needed for sprites, text, clear operations, and background capture if they draw inside the moving playfield. The experiment can limit its visible content to tiles and one sprite, but it must prove that sprite restore happens before a camera-origin change and that capture/draw uses the new origin after edge filling. Existing fixed-origin calls remain unchanged outside the opt-in experiment.

The frame order for a successful tile step is: propose movement; check all collisions; calculate and validate the next camera and physical origin; restore or invalidate the old sprite capture; fill the entering map strip only in addresses proved safe for the current scanout interval; wait for the start of vertical synchronization; switch the CRTC start; commit world position, camera, and origin together; capture and draw the sprite using the new origin. If a check fails before commit, retain all previous positions and the display origin, set a stage-specific failure code, and allow the test pass to restart. If work cannot complete before the next displayed frame, the step fails the one-frame performance gate.

### 4. Decide whether to extract framework support

The hardware path passes only if it moves the displayed image in all four directions on both target modes, returns through reverse steps, fills entering strips without stale pixels or tearing, keeps sprite backgrounds correct, and completes each tile step within one 50 Hz frame on CPC 464 and 6128 emulator configurations. The test must compare observed CRTC state, displayed pixels, and the complete overlapping interior address set (or a write trace) so a software redraw cannot appear to pass. Only documented sprite and strip writes may be excluded. Missing emulator configurations make the gate **unverified**, never passed. Available real-hardware observations are recorded separately and do not substitute for the complete emulator matrix.

If the experiment passes, the design can extract a small opt-in video-origin owner that coordinates the CRTC start and screen-address lookup while preserving old fixed-origin APIs. The example keeps collision and follow policy until another consumer demonstrates a shared need. If it fails, compare the measured existing full redraw with a software shift-and-edge-fill path; selecting that fallback requires a new design decision. Pixel-level scroll remains a separate stage after these measurements.

## Risks and Mitigations

* **CRTC granularity and row layout:** The proposed register values may produce different display starts or wraps on target configurations. Use the sprite-free candidate sweep first, compare actual pixels and CRTC state, and stop the hardware branch if no model matches.
* **Visible-memory overlap and RAM capacity:** A new strip may alias the current display or the union of camera origins may consume RAM needed by code or assets. Enumerate every displayed address and reserve the union before placing assets; reject a transition without a safe write interval.
* **Sprite and fixed-origin address mismatch:** Existing tile, sprite, text, and clear routines use a fixed line table. Keep the hardware pass local and per-scanline, and disable fixed-origin drawing in that pass. Do not expose a framework origin API until all writers have a specified contract.
* **Frame time and visual stability:** Edge fill or sprite work may miss the next visible frame. Require one-frame completion with no tearing, stale strip, or sprite remnant; otherwise record functional behavior and fail the performance gate.
* **Machine coverage and compatibility:** The BluePixel adapter covers CPC 6128, while the other emulator harness can select CPC 464. Require both emulated machines in both modes for a pass; mark missing coverage unverified. Keep existing profiles and APIs unchanged. This local video experiment processes no private data and adds no network or authentication surface.

## Alternatives Considered

### Redraw the full viewport after every camera tile change

* **Mechanism:** Keep the current camera fields and call the existing full-view renderer whenever they change.
* **Benefit:** No new CRTC addressing path; it gives a direct behavior baseline and keeps the current video routines coherent.
* **Cost and failure condition:** The renderer checks and draws every tile, while sprite backgrounds must be restored or invalidated. The measured cost of a 5×4 view does not establish the cost of a 16×16 view. It fails as the general solution if the measured camera step cannot meet the accepted frame budget or visibly tears.
* **Decision:** Retained as the first baseline experiment. It is not selected as the final scrolling mechanism without measurements.

### Shift video bytes in software and draw the entering strip

* **Mechanism:** Copy the existing playfield by a whole tile in video memory and draw only the row or column that enters view.
* **Benefit:** Keeps the CRTC start fixed, so current screen-address calculations are easier to reuse.
* **Cost and failure condition:** The copy touches much of the playfield at each camera step and can exceed the frame budget or tear while the beam displays it. The copy must handle all four directions and CPC screen-memory ordering.
* **Decision:** Retained as a measured fallback if the CRTC experiment cannot provide a safe memory layout. Adoption needs a separate decision after timing and visual comparison.

### Let game code write the CRTC start directly

* **Mechanism:** Update R12/R13 when the game camera moves, leaving existing framework video calls unchanged.
* **Benefit:** Few new framework entry points in a short prototype.
* **Cost and failure condition:** The CRTC would display a shifted area while the fixed line table, tile routines, sprite capture, text, and clearing still address the old area. It fails as a reusable framework contract even if a simple pattern appears to scroll.
* **Decision:** Rejected as the framework design. The isolated feasibility experiment may write CRTC registers to measure hardware behavior, but it must not claim that existing drawing APIs remain valid afterward.

### Add a generic camera and collision module immediately

* **Mechanism:** Put the follow zone, map clamp, solid-tile checks, object checks, and character checks behind one framework interface before the example exists.
* **Benefit:** A game could make one call for movement and scrolling.
* **Cost and failure condition:** Objects and characters have game-specific rules, and no second consumer has established a shared follow policy. The module would couple those rules to physical video state before either is measured.
* **Decision:** Deferred. Keep the first camera policy and object collision examples local; extract only behavior proven reusable.

### Design pixel scrolling in this stage

* **Mechanism:** Include byte rotation, pre-shifted graphics, or other pixel-level drawing in the first API.
* **Benefit:** Could avoid revisiting an interface later.
* **Cost and failure condition:** It adds memory and CPU choices before the tile-scroll result is known. A classic CPC cannot rely on the CPC Plus ASIC to make this choice trivial.
* **Decision:** Deferred to the second stage. The author selected classic CPC 464 and 6128 support, so an ASIC-only path is outside this design.

## Detailed Implementation Plan

The implementation will deliver two playable camera-and-collision examples and two separately observable CRTC experiments, ending at a measured feasibility gate. It will not publish a new framework video API before the physical address and timing results are known. The following is one ordered file-change list; generated evidence under `build/scroll-evidence/` is test output, not source.

1. **Create `./framework/profiles/scroll-mode0-128x128.json` and `./framework/profiles/scroll-mode1-128x128.json`; modify `./Makefile` and `./tests/test_video.py`.** Both profiles use a `0xC000` 16 KiB video window, height 128, R6=16, R9=7, initial R12=`0x30`, and R13=`0x00`. Start with Mode 0 width 64 bytes/R1=32/R2=42 and Mode 1 width 32 bytes/R1=16/R2=34. These R2 values are centering candidates derived from the current standard timing, not confirmed physical positions. Mark both profiles experimental. The Makefile generates them; the tests check mode, width, height, fixed-origin addresses, CRTC fields, and window bounds. Both examples must call `fwk_video_configure_crtc` after `fwk_video_init` and before clearing or drawing; a screenshot confirms actual 128×128 geometry before timing begins. Existing profiles are unchanged.

2. **Modify `./tools/build/video_model.py` and `./tests/test_video.py`.** Add an origin-aware address query to the existing model with inputs of profile, R1/R6/R9, R12/R13, video page, and screen byte/scanline. Interpret the CRTC memory address and raster address using the observed CPC mapping, including 16 KiB wrap; keep candidate horizontal and vertical start increments explicit parameters until the pattern probe confirms them. Return every visible physical address, the current/next overlap, entering bytes, address aliases, and the union over camera positions. A transition is safe only if every pre-switch fill address lies outside the currently displayed set, or a measured blank interval covers the write. Check this for the full 9×9 camera-position grid, all four directions, reversals, wrap and reserved-RAM overlap. Do not add a second independent `scroll_model.py`.

3. **Create `./examples/scroll0/Makefile`, `./examples/scroll0/glasnost.manifest.json`, `./examples/scroll0/main.s`, `./examples/scroll0/README.md`, and the corresponding four files in `./examples/scroll1/`.** Each manifest selects its new profile and `core/system.s`, `core/input.s`, `video/video.s`, `video/sprite.s`, `extensions/tilemap.s`, and `extensions/tilemap_render.s`; its only game source is local `main.s`. The baseline uses the existing full-view renderer. Both examples use the same 24×24 tile map, the exact player and obstacle rectangles above, 8×8 tiles, an 8×8 opaque player, and recognizable edge patterns. Player top-left is `(92,92)`, camera starts at tile `(4,4)`, and valid camera coordinates are 0–8 per axis. For every proposed 2-pixel Mode 0 or 4-pixel Mode 1 step, test every solid tile touched by the full 8×8 player rectangle, both blocking rectangles, and the world boundary. If blocked, change nothing. Otherwise calculate the 64×64 default camera zone from independently named horizontal/vertical constants, clamp the camera, validate the physical origin if the hardware pass is active, and commit world, screen, camera and origin together. A failed hardware check retains all positions and the prior image, records a code, and returns the test pass to its ready state. The readmes state `O/P/Q/A` controls, one cardinal direction per update, build/run commands, and the status fields. The baseline timing uses the same tiles and sprite as the hardware pass.

4. **Add the candidate probe and origin-aware hardware path within those two `main.s` files.** Boot to a ready state with a small RAM mailbox: `game_pass` selects 1=baseline, 2=sprite-free pattern, 3=edge-fill-and-sprite; `game_command` selects 1=west, 2=east, 3=north, 4=south, or 5=reset; `game_sequence` is written by the host and `game_ack` copies it only after exactly one command completes. `game_status` is `0x5A` ready, `0x52` running, `0x43` complete, or `0x46` failed. `game_failure` is 0=none, 1=invalid origin, 2=unsafe fill, 3=geometry mismatch, or 4=time overrun; an ordinary collision completes with unchanged positions and sets a separate `game_blocked` byte. Expose world/screen/camera coordinates, requested and committed R12/R13, and frame counter as named symbols. The host sets `game_pass`, writes reset command 5 with a new sequence, waits for `game_ack` and ready, then sends one direction command per new sequence and waits for complete or failed before sampling. Keyboard controls use the same one-step routine in baseline mode; tests use the mailbox to avoid held-key repeat ambiguity. Reset restores the starting map, player, camera and CRTC origin.

   The pattern pass sweeps a bounded set of one-register increments and decrements around R12=`0x30`, R13=`0x00`, then tests one vertical tile increment and reversal; it records actual CRTC values and address-distinct screen pixels without edge filling or sprites. Use these observations to confirm or reject the model's candidate increments and rebuild the hardware pass with confirmed origins. The hardware pass permits only model-approved camera transitions. It draws tiles and the player through local per-scanline copy routines that resolve every physical row from the current origin; no existing fixed-origin tile, sprite, text, or clear routine is called after the first CRTC shift. An opaque 8×8 sprite needs 32 capture bytes in Mode 0 and 16 in Mode 1. Clip every row to the 128×128 playfield and handle 16 KiB wrap per row. Restore or invalidate old capture before switching; fill only model-approved entering bytes; synchronize the R12/R13 commit to VSYNC start; then capture and draw at the new origin. Full-view rendering remains disabled until a reset returns to baseline. If a pre-commit check fails after restoration, redraw the old sprite before returning ready so the visible state is unchanged.

5. **Create `./tests/bluepixel_scroll_smoke.py`; modify `./tests/emulator_smoke.py`.** The BluePixel test runs the complete Mode 0/1 witness on CPC 6128 using its existing `run`, `read`, `write`, `capture`, and input APIs. Extend the existing emulator smoke's `--model 464` path with the same command route and pixel/RAM checks for CPC 464, as well as explicit boot and movement checks in the full-catalog run. Both tests use the mailbox sequence/acknowledgement so each camera step is sampled once. Compare actual CRTC registers from the emulator state or capture metadata with mirrored values, screenshot pixels with the address-distinct expected pattern, and the entire overlapping interior backing-address set before/after. Permit only the enumerated sprite restore/capture and entering-strip writes; a single unchanged byte is insufficient. Drive each direction, reversal, camera edge, and each obstacle from deterministic starting states and compare exact world/screen/camera coordinates. Save `build/scroll-evidence/<machine>/<mode>/<sequence>.json` and `.png`; each JSON records machine and ROM/version, mode, pass, command, world/screen/camera before and after, requested/committed/observed origin, allowed write set, interior comparison, status/failure, starting/ending frame, and T-states where available. BluePixel's 6128-only adapter remains unchanged. A missing 464 or 6128 setup is **unverified**, not a pass.

6. **Modify `./docs/design/validation.md` and `./docs/design/performance.md`, then publish the experimental examples.** Record the complete two-mode by two-machine emulator matrix, geometry, address-model comparison, screenshot and RAM witnesses, worst step duration, full-redraw baseline, and any failed stage; physical-hardware observations get separate rows. The commit boundary is VSYNC start, and the first-stage performance limit is one 50 Hz frame (about 79,872 Z80 T-states) from accepting a command through collision, old-sprite restoration, entering-strip fill, CRTC switch, new capture/draw, and visible result. A step over this limit is functionally observed but fails the performance gate. No tearing, stale strip or sprite remnant is permitted in captured frames. If layout, correctness, coverage, or timing fails, record the result and choose a revised layout or software-shift fallback in a follow-up decision. After the result is recorded, publish both examples as **experimental** with the measured status, including a failed or unverified result; this does not claim framework-wide scroll support.

7. **Modify `./tests/test_program_catalog.py`, `./tests/test_release.py`, `./tools/dev/package_release.py`, `./docs/README.md`, `./docs/manual.html`, `./docs/manual.pdf`, `./docs/manual.sha256`, and `./README.md` for that publication.** Add the two public names and their BIN/CDT media to catalog/release expectations, derive the archive count from the actual media list, and update the release packager's hard-coded playable-example list and archive README instructions. Label both examples experimental and link their measured result; update example counts, manual entries, controls, and build/run directions. Regenerate the PDF and checksum using `python3 tools/dev/build_manual.py`. These release changes follow the feasibility report even if the result is a documented failure, so the public material never suggests unverified framework support.

**Verification sequence:** Run `python3 -m unittest tests.test_video`, `python3 tools/build/build_examples.py scroll0 scroll1`, `python3 tests/bluepixel_scroll_smoke.py` for CPC 6128, and `python3 tests/emulator_smoke.py --model 464 scroll0 scroll1` for CPC 464, then inspect the generated evidence. Run `make test` and `python3 tools/dev/build_manual.py` after publication files change. A passing build or static address model alone cannot satisfy the hardware gate. The two-mode by two-machine emulator matrix, exact per-step screen/RAM evidence, and the one-frame measurement determine the result. A later design may extract an opt-in framework video-origin owner and address contracts for tile, sprite, text and clear writers; pixel-level scrolling remains a separate stage.

*Drafted with EGM*
