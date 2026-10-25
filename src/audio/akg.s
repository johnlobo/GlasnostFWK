;; Optional Arkos Tracker 3 AKG adapter. No player or song data is bundled:
;; linking this module requires the project's generated _PLY_AKG_* export.
.module fwk_audio_akg

.globl _PLY_AKG_PLAY
.globl _PLY_AKG_INIT
.globl _PLY_AKG_STOP
.globl _PLY_AKG_INITSOUNDEFFECTS
.globl _PLY_AKG_PLAYSOUNDEFFECT
.globl fwk_system_set_irq_callback

.area _DATA
fwk_audio_active:: .db 0

.area _CODE

;; fwk_audio_init_music
;; In: HL=AKG song address, A=subsong. Out: initialized but paused.
;; Modified: player-defined AF,BC,DE,HL. Call outside interrupt context.
fwk_audio_init_music::
    push af
    xor a
    ld (fwk_audio_active), a
    pop af
    jp _PLY_AKG_INIT

;; fwk_audio_init_sfx
;; In: HL=AKG sound-effects table. Modified: player-defined AF,BC,DE,HL.
fwk_audio_init_sfx::
    jp _PLY_AKG_INITSOUNDEFFECTS

;; fwk_audio_start
;; Registers AKG playback as the once-per-frame system IRQ callback.
fwk_audio_start::
    ld a, #1
    ld (fwk_audio_active), a
    ld hl, #fwk_audio_tick
    jp fwk_system_set_irq_callback

;; fwk_audio_stop
;; Stops the player and unregisters the IRQ callback.
fwk_audio_stop::
    xor a
    ld (fwk_audio_active), a
    ld hl, #0
    call fwk_system_set_irq_callback
    jp _PLY_AKG_STOP

;; fwk_audio_play_sfx
;; In: A=effect id, B=inverted volume, C=AY channel 0..2.
fwk_audio_play_sfx::
    jp _PLY_AKG_PLAYSOUNDEFFECT

;; fwk_audio_tick
;; IRQ callback. Preserves both register sets around the generated player.
fwk_audio_tick::
    ld a, (fwk_audio_active)
    or a
    ret z
    exx
    ex af, af'
    push af
    push bc
    push de
    push hl
    call _PLY_AKG_PLAY
    pop hl
    pop de
    pop bc
    pop af
    ex af, af'
    exx
    ret
