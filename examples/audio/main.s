.module example_audio
.include "cpctelera.h.s"
.include "audio/akg.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible
.globl audio_songStart, audio_sfxSoundEffects

.area _DATA
audio_command:: .db 0
audio_command_ack:: .db 0

.area _CODE
_main::
    call fwk_project_init
    call fwk_video_init
    xor a
    call fwk_video_clear_visible

    ld hl, #audio_songStart
    xor a
    call fwk_audio_init_music
    ld hl, #audio_sfxSoundEffects
    call fwk_audio_init_sfx
    call fwk_audio_start

_audio_loop:
    call fwk_system_wait_frame
    ld a, (audio_command)
    or a
    jr z, _audio_loop
    cp #1
    jr z, _audio_play_sfx
    cp #2
    jr z, _audio_stop
    cp #3
    jr z, _audio_start
    jr _audio_ack

_audio_play_sfx:
    ld a, #3
    ld b, #0
    ld c, #FWK_AUDIO_CHANNEL_B
    call fwk_audio_play_sfx
    jr _audio_ack

_audio_stop:
    call fwk_audio_stop
    jr _audio_ack

_audio_start:
    call fwk_audio_start

_audio_ack:
    ld a, (audio_command)
    ld (audio_command_ack), a
    xor a
    ld (audio_command), a
    jr _audio_loop
