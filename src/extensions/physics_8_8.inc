FWK_PHYS88_X = 0
FWK_PHYS88_Y = 2
FWK_PHYS88_VX = 4
FWK_PHYS88_VY = 6
FWK_PHYS88_FRACTION = 8
FWK_PHYS88_STATE_SIZE = 9

FWK_PHYS88_MIN_X = 0
FWK_PHYS88_MAX_X = 1
FWK_PHYS88_MIN_Y = 2
FWK_PHYS88_MAX_Y = 3
FWK_PHYS88_FRICTION = 4
FWK_PHYS88_CONFIG_SIZE = 5

.macro FWK_PHYS88_CONFIG label, min_x, max_x, min_y, max_y, friction
label:
    .db min_x, max_x, min_y, max_y, friction
.endm
