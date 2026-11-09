;; Optional Arkos Tracker 3 AKG adapter for CPCtelera Next's bundled player.
;; Song and sound-effect data remain game-owned and are not bundled here.
.module fwk_audio_akg

.globl _cpct_PLY_AKG_Play
.globl _cpct_PLY_AKG_Init
.globl _cpct_PLY_AKG_Stop
.globl _cpct_PLY_AKG_InitSoundEffects
.globl _cpct_PLY_AKG_PlaySoundEffect
.globl fwk_system_set_irq_callback

.area _DATA
fwk_audio_active:: .db 0
fwk_audio_tick_count:: .dw 0
fwk_audio_sfx_count:: .db 0

.area _CODE

;; fwk_audio_init_music
;; In: HL=AKG song address, A=subsong. Out: initialized but paused.
;; Modified: player-defined AF,BC,DE,HL. Call outside interrupt context.
fwk_audio_init_music::
    push af
    xor a
    ld (fwk_audio_active), a
    ld (fwk_audio_tick_count), a
    ld (fwk_audio_tick_count + 1), a
    ld (fwk_audio_sfx_count), a
    pop af
    ld e, a
    jp _cpct_PLY_AKG_Init

;; fwk_audio_init_sfx
;; In: HL=AKG sound-effects table. Modified: player-defined AF,BC,DE,HL.
fwk_audio_init_sfx::
    jp _cpct_PLY_AKG_InitSoundEffects

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
    jp _cpct_PLY_AKG_Stop

;; fwk_audio_play_sfx
;; In: A=effect id, B=inverted volume, C=AY channel 0..2.
fwk_audio_play_sfx::
    push af
    ld a, (fwk_audio_sfx_count)
    inc a
    ld (fwk_audio_sfx_count), a
    pop af
    ld d, a
    ld l, b
    ld h, #0
    push hl
    ld a, d
    ld l, c
    call _cpct_PLY_AKG_PlaySoundEffect
    ret

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
    call _cpct_PLY_AKG_Play
    ld hl, (fwk_audio_tick_count)
    inc hl
    ld (fwk_audio_tick_count), hl
    pop hl
    pop de
    pop bc
    pop af
    ex af, af'
    exx
    ret
