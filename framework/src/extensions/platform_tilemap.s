;; Optional tile collision resolver for the compact platform state.
.module fwk_platform_tilemap
.include "extensions/platform_tilemap.inc"

.globl fwk_tilemap_query

.area _CODE

;; fwk_platform_tilemap_resolve
;; Call after fwk_physics_platform_step.
;; In: IY=platform state, IX=read-only tilemap descriptor.
;; Out: A=collision mask (left/right/ceiling/floor/support lost).
;; Solid tiles block every axis. One-way tiles block only downward crossings
;; and support an entity already grounded on them. Invalid/OOB queries pass.
;; Modified: AF,BC,DE,HL. IX/IY preserved. Reentrant for separate state.
fwk_platform_tilemap_resolve::
    ld d, #0
    ld a, FWK_PLATFORM_VX(iy)
    or a
    jp z, _fwk_pt_vertical
    bit 7, a
    jr nz, _fwk_pt_left

    ;; Moving right: query top and bottom at the new leading edge.
    ld a, FWK_PLATFORM_X(iy)
    add FWK_PLATFORM_WIDTH(iy)
    dec a
    ld c, a
    ld a, FWK_PLATFORM_Y(iy)
    sub FWK_PLATFORM_VY(iy)
    ld b, a
    push de
    call fwk_tilemap_query
    pop de
    jr c, _fwk_pt_right_bottom
    cp #FWK_TILE_SOLID
    jr z, _fwk_pt_hit_right
_fwk_pt_right_bottom:
    ld a, FWK_PLATFORM_Y(iy)
    sub FWK_PLATFORM_VY(iy)
    add FWK_PLATFORM_HEIGHT(iy)
    dec a
    ld b, a
    push de
    call fwk_tilemap_query
    pop de
    jr c, _fwk_pt_vertical
    cp #FWK_TILE_SOLID
    jr nz, _fwk_pt_vertical
_fwk_pt_hit_right:
    ld a, FWK_TILEMAP_X_SIZE(ix)
    dec a
    cpl
    and c
    sub FWK_PLATFORM_WIDTH(iy)
    ld FWK_PLATFORM_X(iy), a
    ld FWK_PLATFORM_VX(iy), #0
    set FWK_PLATFORM_HIT_RIGHT_BIT, d
    jr _fwk_pt_vertical

_fwk_pt_left:
    ld c, FWK_PLATFORM_X(iy)
    ld a, FWK_PLATFORM_Y(iy)
    sub FWK_PLATFORM_VY(iy)
    ld b, a
    push de
    call fwk_tilemap_query
    pop de
    jr c, _fwk_pt_left_bottom
    cp #FWK_TILE_SOLID
    jr z, _fwk_pt_hit_left
_fwk_pt_left_bottom:
    ld a, FWK_PLATFORM_Y(iy)
    sub FWK_PLATFORM_VY(iy)
    add FWK_PLATFORM_HEIGHT(iy)
    dec a
    ld b, a
    push de
    call fwk_tilemap_query
    pop de
    jr c, _fwk_pt_vertical
    cp #FWK_TILE_SOLID
    jr nz, _fwk_pt_vertical
_fwk_pt_hit_left:
    ld a, FWK_TILEMAP_X_SIZE(ix)
    dec a
    cpl
    and c
    add FWK_TILEMAP_X_SIZE(ix)
    ld FWK_PLATFORM_X(iy), a
    ld FWK_PLATFORM_VX(iy), #0
    set FWK_PLATFORM_HIT_LEFT_BIT, d

_fwk_pt_vertical:
    ld a, FWK_PLATFORM_VY(iy)
    or a
    jp z, _fwk_pt_support
    bit 7, a
    jr nz, _fwk_pt_ceiling

    ;; Moving down: solid and one-way tiles may be landed upon.
    ld a, FWK_PLATFORM_Y(iy)
    add FWK_PLATFORM_HEIGHT(iy)
    dec a
    ld b, a
    ld c, FWK_PLATFORM_X(iy)
    push de
    call fwk_tilemap_query
    pop de
    jr c, _fwk_pt_floor_right
    cp #FWK_TILE_SOLID
    jr z, _fwk_pt_land
    cp #FWK_TILE_ONE_WAY
    jr nz, _fwk_pt_floor_right
    call _fwk_pt_one_way_crossed
    jr nc, _fwk_pt_land
_fwk_pt_floor_right:
    ld a, FWK_PLATFORM_X(iy)
    add FWK_PLATFORM_WIDTH(iy)
    dec a
    ld c, a
    push de
    call fwk_tilemap_query
    pop de
    jp c, _fwk_pt_done
    cp #FWK_TILE_SOLID
    jr z, _fwk_pt_land
    cp #FWK_TILE_ONE_WAY
    jp nz, _fwk_pt_done
    call _fwk_pt_one_way_crossed
    jp c, _fwk_pt_done
_fwk_pt_land:
    ld a, FWK_TILEMAP_Y_SIZE(ix)
    dec a
    cpl
    and b
    sub FWK_PLATFORM_HEIGHT(iy)
    ld FWK_PLATFORM_Y(iy), a
    ld FWK_PLATFORM_VY(iy), #0
    res FWK_PLATFORM_AIRBORNE_BIT, FWK_PLATFORM_FLAGS(iy)
    set FWK_PLATFORM_TILE_GROUNDED_BIT, FWK_PLATFORM_FLAGS(iy)
    set FWK_PLATFORM_HIT_FLOOR_BIT, d
    jp _fwk_pt_done

_fwk_pt_ceiling:
    ld b, FWK_PLATFORM_Y(iy)
    ld c, FWK_PLATFORM_X(iy)
    push de
    call fwk_tilemap_query
    pop de
    jr c, _fwk_pt_ceiling_right
    cp #FWK_TILE_SOLID
    jr z, _fwk_pt_hit_ceiling
_fwk_pt_ceiling_right:
    ld a, FWK_PLATFORM_X(iy)
    add FWK_PLATFORM_WIDTH(iy)
    dec a
    ld c, a
    push de
    call fwk_tilemap_query
    pop de
    jr c, _fwk_pt_done
    cp #FWK_TILE_SOLID
    jr nz, _fwk_pt_done
_fwk_pt_hit_ceiling:
    ld a, FWK_TILEMAP_Y_SIZE(ix)
    dec a
    cpl
    and b
    add FWK_TILEMAP_Y_SIZE(ix)
    ld FWK_PLATFORM_Y(iy), a
    ld FWK_PLATFORM_VY(iy), #0
    set FWK_PLATFORM_AIRBORNE_BIT, FWK_PLATFORM_FLAGS(iy)
    res FWK_PLATFORM_TILE_GROUNDED_BIT, FWK_PLATFORM_FLAGS(iy)
    set FWK_PLATFORM_HIT_CEILING_BIT, d
    jr _fwk_pt_done

_fwk_pt_support:
    bit FWK_PLATFORM_TILE_GROUNDED_BIT, FWK_PLATFORM_FLAGS(iy)
    jr z, _fwk_pt_done
    ld a, FWK_PLATFORM_Y(iy)
    add FWK_PLATFORM_HEIGHT(iy)
    ld b, a
    ld c, FWK_PLATFORM_X(iy)
    push de
    call fwk_tilemap_query
    pop de
    jr c, _fwk_pt_support_right
    cp #FWK_TILE_SOLID
    jr z, _fwk_pt_done
    cp #FWK_TILE_ONE_WAY
    jr z, _fwk_pt_done
_fwk_pt_support_right:
    ld a, FWK_PLATFORM_X(iy)
    add FWK_PLATFORM_WIDTH(iy)
    dec a
    ld c, a
    push de
    call fwk_tilemap_query
    pop de
    jr c, _fwk_pt_lose_support
    cp #FWK_TILE_SOLID
    jr z, _fwk_pt_done
    cp #FWK_TILE_ONE_WAY
    jr z, _fwk_pt_done
_fwk_pt_lose_support:
    set FWK_PLATFORM_AIRBORNE_BIT, FWK_PLATFORM_FLAGS(iy)
    res FWK_PLATFORM_TILE_GROUNDED_BIT, FWK_PLATFORM_FLAGS(iy)
    set FWK_PLATFORM_SUPPORT_LOST_BIT, d

_fwk_pt_done:
    ld a, d
    ret

;; B=current bottom, VY=positive. Carry clear only when the previous bottom was
;; strictly above this tile's top edge.
_fwk_pt_one_way_crossed:
    ld a, b
    sub FWK_PLATFORM_VY(iy)
    ld c, a
    ld a, FWK_TILEMAP_Y_SIZE(ix)
    dec a
    cpl
    and b
    cp c
    jr c, _fwk_pt_one_way_no
    jr z, _fwk_pt_one_way_no
    or a
    ret
_fwk_pt_one_way_no:
    scf
    ret
