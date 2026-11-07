;; Common definitions of this project, imported by every .s file: framework
;; headers, .globl declarations, constants and macros. The .s files hold only
;; code and data.
.include "cpctelera.h.s"
.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "core/ecs_animation.inc"
.include "extensions/behavior.inc"
.include "video/ecs_render.inc"
.include "assets/generated/assets.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_get_ptr
.globl fwk_input_init, fwk_input_set_bindings, fwk_input_update, fwk_input_held
.globl fwk_text_init, fwk_text_draw
.globl fwk_ecs_system_input
.globl cpct_setPalette_asm
.globl game_palette, game_ship_pixels, game_ship_pixels2
.globl game_drone_pixels, game_drone_pixels2

;; Actions the keyboard bindings produce. The first three are understood by the
;; framework input system (fwk_ecs_system_input); UP and DOWN are handled by
;; the steering system in main.s.
GAME_INPUT_LEFT  = 0x01
GAME_INPUT_RIGHT = 0x02
GAME_INPUT_UP    = 0x08
GAME_INPUT_DOWN  = 0x10

;; Entity types, free for your game to use.
GAME_T_PLAYER = 1
GAME_T_DRONE  = 2

;; One manager holds the player and the three drones.
GAME_CAP = 4

;; Where the player may go (screen bytes and lines). The text takes the top.
GAME_X_MAX = 76
GAME_Y_MIN = 44
GAME_Y_MAX = 192
GAME_SPEED_Y = 2

;; Text positions (byte column, scanline).
GAME_TEXT_X = 4
GAME_TEXT_Y_WELCOME = 4
GAME_TEXT_Y_TITLE = 16
GAME_TEXT_Y_HELP = 28

;; Drone patrol: the first leg is half a leg long, so a drone sweeps 20 bytes
;; either side of where it starts.
GAME_DRONE_FIRST_LEG = 20
GAME_DRONE_LEG = 40

;; Frames of an animation last this many calls of the animation system.
GAME_ANIM_TICKS = 8

;; Spawn row: components, type, x, y, width and height (bytes, lines), sprite,
;; behavior program, animation descriptor (0 = none).
.macro GAME_ROW comps, type, x, y, w, h, sprite, program, anim
    .dw comps
    .db type, x, y, w, h
    .dw sprite
    .dw program, anim
.endm

GAME_PLAYER_COMPS = ECS_C_RENDER|ECS_C_MOTION|ECS_C_INPUT|ECS_C_ANIMATION
GAME_DRONE_COMPS  = ECS_C_RENDER|ECS_C_MOTION|ECS_C_BEHAVIOR|ECS_C_ANIMATION
