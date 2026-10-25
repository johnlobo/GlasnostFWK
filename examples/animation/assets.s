.module example_animation_assets

.area _DATA
animation_frame_0:: .db 0xF0
animation_frame_1:: .db 0x0F
animation_frame_2:: .db 0xAA

animation_descriptor::
    .db 3
    .db 4
    .dw animation_frame_0, animation_frame_1, animation_frame_2
