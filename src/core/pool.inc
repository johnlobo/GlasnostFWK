FWK_POOL_BASE_LO = 0
FWK_POOL_BASE_HI = 1
FWK_POOL_CAPACITY = 2
FWK_POOL_ELEMENT_SIZE = 3
FWK_POOL_COUNT = 4
FWK_POOL_DESCRIPTOR_SIZE = 5

.macro FWK_POOL_DESCRIPTOR name, storage, capacity, element_size
name::
    .dw storage
    .db capacity
    .db element_size
    .db 0
.endm
