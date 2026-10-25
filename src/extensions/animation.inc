;; Looping animation descriptor:
;;   byte frame_count (1..255)
;;   byte duration in tick calls (1..255)
;;   word frame pointers[frame_count]
FWK_ANIM_DESC_COUNT = 0
FWK_ANIM_DESC_DURATION = 1
FWK_ANIM_DESC_FRAMES = 2

;; Per-animation mutable state. Callers own and allocate this storage.
FWK_ANIM_STATE_DESCRIPTOR = 0
FWK_ANIM_STATE_FRAME = 2
FWK_ANIM_STATE_REMAINING = 3
FWK_ANIM_STATE_SIZE = 4

.globl fwk_anim_clear
.globl fwk_anim_set
.globl fwk_anim_tick
