.module example_audio
.include "cpctelera.h.s"
.include "audio/akg.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible
.globl audio_songStart, audio_sfxSoundEffects

.area _DATA
;; Mailbox driven from outside (the emulator test writes it): 0=none, 1=play SFX,
;; 2=stop music, 3=start music. The loop clears it once handled.
audio_command:: .db 0
;; Last command that was handled, so the test can see that it was consumed.
audio_command_ack:: .db 0

.area _CODE
;; ----------------------------------------------------------------------------
;; _main
;;   Program entry. Starts the framework and the AKG music, then polls the
;;   audio_command mailbox once per frame and runs the requested action.
;;   In : none.
;;   Out: never returns.
;;   Clobbers: all (never returns)
;;   Notes: music plays from the IRQ callback installed by fwk_audio_start, not
;;          from this loop. The framework and AKG callees' exact register use is
;;          not documented, so nothing is assumed preserved.
;; ----------------------------------------------------------------------------
_main::
    call fwk_project_init
    call fwk_video_init
    xor a                           ; fill byte 0: blank screen
    call fwk_video_clear_visible

    ;; Load the song (subsong 0) and the sound-effect table into the AKG player.
    ;; Music stays paused until fwk_audio_start registers the IRQ callback.
    ld hl, #audio_songStart
    xor a
    call fwk_audio_init_music
    ld hl, #audio_sfxSoundEffects
    call fwk_audio_init_sfx
    call fwk_audio_start

_audio_loop:                        ; poll the mailbox once per frame
    call fwk_system_wait_frame
    ld a, (audio_command)
    or a
    jr z, _audio_loop               ; 0: nothing to do
    cp #1
    jr z, _audio_play_sfx
    cp #2
    jr z, _audio_stop
    cp #3
    jr z, _audio_start
    jr _audio_ack                   ; unknown command: acknowledge and ignore

_audio_play_sfx:                    ; command 1: effect 3 on channel B, full volume
    ld a, #3                        ; effect ids start at 1 (0 is not valid)
    ld b, #0                        ; inverted volume: 0 = loudest
    ld c, #FWK_AUDIO_CHANNEL_B
    call fwk_audio_play_sfx
    jr _audio_ack

_audio_stop:                        ; command 2: stop the player and the IRQ callback
    call fwk_audio_stop
    jr _audio_ack

_audio_start:                       ; command 3: register the callback again (falls into ack)
    call fwk_audio_start

_audio_ack:                         ; publish the handled command, then clear the mailbox
    ld a, (audio_command)
    ld (audio_command_ack), a
    xor a
    ld (audio_command), a
    jr _audio_loop
