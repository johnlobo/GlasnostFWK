;; GlasnostFWK ECS 2.0 entity animation: public ABI (docs/ecs-abi-2.0.md, 10).
;; Descriptors use the same layout as extensions/animation.inc and may be shared:
;;   byte count (1..255), byte duration in system calls (1..255),
;;   word frame sprite pointers[count].
;; count or duration of 0 is undefined and silent. The descriptor carries no
;; sprite size: ECS_E_WIDTH/HEIGHT are never modified.

;; fwk_ecs_system_animation
;; In: IX=manager. Out: carry clear and A=0, or carry set and A=FWK_ECS_ERR_*
;; (those of fwk_ecs_system_run). Every ACTIVE entity with the ANIMATION bit and
;; a descriptor counts its timer down once per call; when it reaches zero the
;; timer reloads the descriptor duration, the frame advances (wrapping) and
;; ECS_E_RENDER_SPRITE is set to that frame's pointer with ECS_RENDER_DIRTY.
.globl fwk_ecs_system_animation

;; fwk_ecs_anim_set
;; In: IY=entity, HL=descriptor or 0. Out: carry clear and A=0. Preserves IX/IY.
;; A different descriptor restarts at frame 0 with a full timer, sets the sprite
;; and DIRTY; HL=0 stops the animation and keeps the current sprite. Selecting
;; the descriptor already running changes nothing (frame and timer continue);
;; a TIMER of 0 means "not started" and starts it, so entities copied from a
;; template that holds a descriptor still start. Called before the system in the
;; same frame, frame 0 lasts one call less; called after, the full duration.
.globl fwk_ecs_anim_set
