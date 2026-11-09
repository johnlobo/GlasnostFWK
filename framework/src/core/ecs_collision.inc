;; GlasnostFWK ECS 2.0 entity collision: public ABI (docs/reference/ecs-abi-2.0.md, 9).

ECS_COLLISION_TOUCHING = 0x01   ; default channel (bit 0 of ECS_E_COLLISION_CONTACT)

ECS_COLLISION_ENTER    = 1
ECS_COLLISION_STAY     = 2
ECS_COLLISION_EXIT     = 3

;; fwk_ecs_collide
;; In: IX=manager of the targets, IY=subject entity, BC=component mask the
;;     targets must have, HL=callback, E=channel: one bit of
;;     ECS_E_COLLISION_CONTACT that holds this pass's ENTER/STAY/EXIT state
;;     (use a different bit for each group of targets tested for the same
;;     subject; E=0 keeps no state, every contact is ENTER).
;; Callback: IX=manager, IY=target (0 on EXIT), HL=subject, A=ENTER|STAY|EXIT.
;;     Carry set stops the pass (A is the error, 0 becomes ERR_CALLBACK).
;; Out: carry clear and A=0, or carry set and A=FWK_ECS_ERR_*. IX/IY preserved.
.globl fwk_ecs_collide
