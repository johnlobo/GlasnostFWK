#!/usr/bin/env python3
"""Differential fuzz for the ECS collision system: model, cases and runner.

The model is written from docs/ecs-abi-2.0.md 9 and 9.1, independently from
tools/ecs_collision_model.py (which drives the 35-step examples/ecscollision
scenario), so the two agree only if both read the contract the same way.

usage: python3 tests/ecs_collision_fuzz.py [--emulator PATH] SUITE [SUITE...]
       python3 tests/ecs_collision_fuzz.py --list

Needs `python3 tools/build_examples.py ecsfuzz` and
`python3 tools/build_test_disk.py ecsfuzz` first. Correctness suites finish in
minutes; the perf* suites measure frames per call and are not pass/fail.
"""
from __future__ import annotations
import json, os, random, re, signal, subprocess, sys, time, urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EMULATOR = ROOT.parent / "tools" / "amspirit-lite" / "run.sh"
ENT = 26
ACTIVE, PENDING, DISABLED, FREE = 1, 2, 3, 0
ERR_ARG, ERR_MGR, ERR_BUSY, ERR_CB, ERR_OVF = 1, 2, 6, 9, 0x0A

# cbmode bits
M_DEST_A, M_DEST_B, M_NULL, M_UNINIT, M_LOCKB, M_LOCKA = 0x01, 0x02, 0x20, 0x10, 0x40, 0x80


@dataclass
class Call:
    mode: int = 0
    abort_k: int = 0
    abort_code: int = 0
    mods: list = field(default_factory=list)  # (mgr, slot, status, roles, x, y, w, h)


@dataclass
class Case:
    na: int
    nb: int
    evcap: int
    paircap: int
    calls: list
    name: str = ""


def blob(cases):
    out = bytearray()
    for c in cases:
        out += bytes((c.na, c.nb, c.evcap, c.paircap, len(c.calls)))
        for k in c.calls:
            out += bytes((k.mode, k.abort_k, k.abort_code, len(k.mods)))
            for m in k.mods:
                out += bytes(m)
    out.append(0)
    return bytes(out)


class Model:
    def __init__(self, case, base_a, base_b):
        self.c = case
        self.ba, self.bb = base_a, base_b
        self.ent = {}  # (mgr,slot) -> dict
        self.pairs = []
        self.events = []
        self.flags = 0
        self.pcount = 0
        self.records = []

    def ptr(self, key):
        m, s = key
        return (self.ba if m == 0 else self.bb) + s * ENT

    def e(self, key):
        return self.ent.get(key, dict(st=FREE, roles=0, comp=1, x=0, y=0, w=0, h=0))

    def part(self, key):
        e = self.e(key)
        return e["st"] == ACTIVE and e["comp"] and (e["roles"] & 3) != 0

    def overlap(self, ka, kb):
        a, b = self.e(ka), self.e(kb)
        if 0 in (a["w"], a["h"], b["w"], b["h"]):
            return False
        return (a["x"] < min(255, b["x"] + b["w"]) and b["x"] < min(255, a["x"] + a["w"])
                and a["y"] < min(255, b["y"] + b["h"]) and b["y"] < min(255, a["y"] + a["h"]))

    def contact(self, ka, kb):
        if not (self.part(ka) and self.part(kb)):
            return False
        ra, rb = self.e(ka)["roles"] & 3, self.e(kb)["roles"] & 3
        if not ((ra & 1 and rb & 2) or (rb & 1 and ra & 2)):
            return False
        return self.overlap(ka, kb)

    def order(self):
        c = self.c
        if c.nb == 0:
            return [((0, i), (0, j)) for i in range(c.na) for j in range(i + 1, c.na)]
        return [((0, i), (1, j)) for i in range(c.na) for j in range(c.nb)]

    def run(self):
        c = self.c
        for ci, call in enumerate(c.calls):
            for (m, s, st, roles, x, y, w, h) in call.mods:
                self.ent[(m, s)] = dict(st=st, roles=roles & 0x7f, comp=0 if roles & 0x80 else 1, x=x, y=y, w=w, h=h)
            mode = call.mode
            res, carry = 0, 0
            lock_a = 1 if mode & M_LOCKA else 0
            lock_b = 2 if mode & M_LOCKB else 0
            if c.nb == 0:
                lockA = lockB = lock_a | lock_b
            else:
                lockA, lockB = lock_a, lock_b
            cbs = 0
            err = None
            if mode & M_NULL:
                err = ERR_ARG
            elif mode & M_UNINIT:
                err = ERR_MGR
            elif lockA or lockB:
                err = ERR_BUSY
            if err:
                self.rec(ci, err, 1, lockA, lockB, 0, 0)
                self.collect()
                continue
            events, newpairs = [], []
            overflow = False
            contact = set()
            for (ka, kb) in self.order():
                if not self.contact(ka, kb):
                    continue
                contact.add((ka, kb))
                kind = 2 if (ka, kb) in self.pairs else 1
                if len(events) < c.evcap:
                    events.append((ka, kb, kind))
                else:
                    overflow = True
                if len(newpairs) < c.paircap:
                    newpairs.append((ka, kb))
                else:
                    overflow = True
            for p in self.pairs:
                if p in contact:
                    continue
                if len(events) < c.evcap:
                    events.append((p[0], p[1], 3))
                else:
                    overflow = True
            self.pairs = newpairs
            self.events = events
            self.flags = 1 if overflow else 0
            self.pcount = len(newpairs)
            res = ERR_OVF if overflow else 0
            carry = 1 if overflow else 0
            for ev in events:
                cbs += 1
                ka, kb, _ = ev
                if mode & M_DEST_A and self.e(ka)["st"] == ACTIVE:
                    self.ent[ka]["st"] = PENDING
                if mode & M_DEST_B and self.e(kb)["st"] == ACTIVE:
                    self.ent[kb]["st"] = PENDING
                if call.abort_k and cbs == call.abort_k:
                    res, carry = (call.abort_code or ERR_CB), 1
                    break
            self.rec(ci, res, carry, 0, 0, cbs, 0)
            self.collect()
        return self.records

    def collect(self):
        for k, e in self.ent.items():
            if e["st"] == PENDING:
                e["st"] = FREE

    def rec(self, ci, res, carry, la, lb, cbs, sb):
        b = bytearray((0, ci, res, carry, self.flags, len(self.events), self.pcount, la, lb, sb))
        for ka, kb, kind in self.events:
            b += self.ptr(ka).to_bytes(2, "little") + self.ptr(kb).to_bytes(2, "little") + bytes((kind,))
        b.append(cbs)
        self.records.append(bytes(b))

    def describe(self, rec):
        return describe(rec, self)


def parse(log):
    recs, pos = [], 0
    while pos + 10 <= len(log):
        n = log[pos + 5]
        end = pos + 10 + 5 * n + 1
        recs.append(log[pos:end])
        pos = end
    return recs


def describe(rec, model=None):
    names = {}
    if model:
        c = model.c
        for i in range(255):
            names[model.ba + i * ENT] = f"A{i}"
            names[model.bb + i * ENT] = f"B{i}"
    ck = {1: "ENTER", 2: "STAY", 3: "EXIT"}
    ev = []
    for i in range(rec[5]):
        o = 10 + 5 * i
        a = int.from_bytes(rec[o:o + 2], "little")
        b = int.from_bytes(rec[o + 2:o + 4], "little")
        ev.append(f"{ck.get(rec[o + 4], rec[o + 4])}({names.get(a, hex(a))},{names.get(b, hex(b))})")
    return (f"call{rec[1]} res={rec[2]:#x} c={rec[3]} flags={rec[4]} pairs={rec[6]} lockA={rec[7]} lockB={rec[8]} "
            f"sbits={rec[9]:#04x} cbs={rec[10 + 5 * rec[5]]} ev=[{' '.join(ev)}]")


# --------------------------------------------------------------- cases
def sat(a, w):
    return min(255, a + w)


def r_arith(axis):
    """Exhaustive combinations on one axis over interesting values."""
    pos = [0, 1, 2, 127, 128, 250, 253, 254, 255]
    siz = [0, 1, 2, 3, 126, 127, 128, 254, 255]
    combos = [(p, s) for p in pos for s in siz]
    cases = []
    for g in range(0, len(combos), 3):
        grp = combos[g:g + 3]
        mods = []
        for i, (p, s) in enumerate(grp):
            x, w, y, h = (p, s, 10, 10) if axis == 0 else (10, 10, p, s)
            mods.append((0, i, ACTIVE, 1, x, y, w, h))
        for j, (p, s) in enumerate(combos):
            x, w, y, h = (p, s, 10, 10) if axis == 0 else (10, 10, p, s)
            mods.append((1, j, ACTIVE, 2, x, y, w, h))
        cases.append(Case(3, 81, 255, 255, [Call(0, 0, 0, mods)], f"arith{axis}-{g}"))
    return cases


def grid(i):
    return (i % 16) * 15, (i // 16) * 12


def r_big():
    cs = []
    # 255 x 255, exactly 255 contacts, evcap == paircap == 255
    def world(evcap, paircap, name, n=255):
        mods = []
        for i in range(n):
            gx, gy = grid(i)
            mods.append((0, i, ACTIVE, 1, gx, gy, 4, 4))
            mods.append((1, i, ACTIVE, 2, gx + 2, gy + 2, 4, 4))
        away = [(1, i, FREE, 0, 0, 0, 0, 0) for i in range(n)]
        back = [(1, i, ACTIVE, 2, grid(i)[0] + 2, grid(i)[1] + 2, 4, 4) for i in range(n)]
        calls = [Call(0, 0, 0, mods[0::2]), Call(0, 0, 0, mods[1::2]), Call(), Call(0, 0, 0, away)]
        return Case(n, n, evcap, paircap, calls, name)
    cs.append(world(255, 255, "big255-255-255"))
    cs.append(world(254, 254, "big255-254-254"))
    return cs


def r_big2():
    """255 colliders vs 255 collisionables with ~2 contacts each (509 pairs), caps 255."""
    mods = []
    for i in range(255):
        gx, gy = grid(i)
        mods.append((0, i, ACTIVE, 1, gx, gy, 4, 4))
        mods.append((1, i, ACTIVE, 2, gx + 2, gy + 2, 16, 4))
    # shift neighbours so B_i also hits A_{i+1}
    return [Case(255, 255, 255, 255, [Call(0, 0, 0, mods[0::2]), Call(0, 0, 0, mods[1::2]), Call(), Call()], "big2")]


def r_single255():
    mods = []
    for k in range(127):
        gx, gy = grid(k)
        mods.append((0, 2 * k, ACTIVE, 1, gx, gy, 4, 4))
        mods.append((0, 2 * k + 1, ACTIVE, 2, gx + 2, gy + 2, 4, 4))
    c = [Case(255, 0, 255, 255, [Call(0, 0, 0, mods), Call(), Call(0, 0, 0, [(0, i, FREE, 0, 0, 0, 0, 0) for i in range(0, 254, 2)]), Call()], "single255")]
    # 40 participants single manager (> 32)
    mods = []
    for k in range(20):
        gx, gy = grid(k)
        mods.append((0, 2 * k, ACTIVE, 1, gx, gy, 4, 4))
        mods.append((0, 2 * k + 1, ACTIVE, 2, gx + 2, gy + 2, 4, 4))
    c.append(Case(40, 0, 255, 255, [Call(0, 0, 0, mods), Call()], "single40"))
    mods = []
    for k in range(17):
        gx, gy = grid(k)
        mods.append((0, 2 * k, ACTIVE, 1, gx, gy, 4, 4))
        mods.append((0, 2 * k + 1, ACTIVE, 2, gx + 2, gy + 2, 4, 4))
    c.append(Case(34, 0, 255, 255, [Call(0, 0, 0, mods), Call()], "single34"))
    mods = []
    for k in range(16):
        gx, gy = grid(k)
        mods.append((0, 2 * k, ACTIVE, 1, gx, gy, 4, 4))
        mods.append((0, 2 * k + 1, ACTIVE, 2, gx + 2, gy + 2, 4, 4))
    c.append(Case(32, 0, 255, 255, [Call(0, 0, 0, mods), Call()], "single32"))
    # 33 A participants vs 1 B, two managers
    mods = [(0, i, ACTIVE, 1, 10 * (i % 20), 10 * (i // 20), 4, 4) for i in range(33)] + [(1, 0, ACTIVE, 2, 0, 0, 200, 200)]
    c.append(Case(33, 1, 255, 255, [Call(0, 0, 0, mods), Call()], "A33"))
    mods = [(0, 0, ACTIVE, 1, 0, 0, 200, 200)] + [(1, i, ACTIVE, 2, 10 * (i % 20), 10 * (i // 20), 4, 4) for i in range(33)]
    c.append(Case(1, 33, 255, 255, [Call(0, 0, 0, mods), Call()], "B33"))
    # 255-slot manager mostly holding 33 participants among 222 non participants (disabled/free)
    mods = [(0, 5 * i, ACTIVE, 3, 3 * i, 3 * i, 4, 4) for i in range(51)]
    c.append(Case(255, 0, 255, 255, [Call(0, 0, 0, mods), Call()], "single255-51part"))
    return c


def r_dense():
    # 40 mutually overlapping entities roles 3 in a single manager, small caps
    mods = [(0, i, ACTIVE, 3, 50 + i, 50, 20, 20) for i in range(30)]
    cs = [Case(30, 0, 100, 100, [Call(0, 0, 0, mods), Call(), Call()], "dense30-100")]
    cs.append(Case(30, 0, 255, 255, [Call(0, 0, 0, mods), Call(), Call()], "dense30-255"))
    cs.append(Case(30, 0, 255, 10, [Call(0, 0, 0, mods), Call(), Call()], "dense30-pair10"))
    cs.append(Case(30, 0, 10, 255, [Call(0, 0, 0, mods), Call(), Call()], "dense30-ev10"))
    return cs


def r_caps():
    cs = []
    mods = [(0, 0, ACTIVE, 1, 10, 10, 4, 4), (0, 1, ACTIVE, 2, 10, 10, 4, 4), (0, 2, ACTIVE, 3, 11, 11, 4, 4)]
    away = [(0, 0, FREE, 0, 0, 0, 0, 0)]
    for ev in (0, 1, 2, 3, 255):
        for pc in (0, 1, 2, 3, 255):
            cs.append(Case(3, 0, ev, pc, [Call(0, 0, 0, mods), Call(), Call(0, 0, 0, away), Call(), Call()], f"caps-{ev}-{pc}"))
    return cs


def r_cb():
    """callbacks destroying entities of either manager, aborts, locks."""
    cs = []
    base = [(0, i, ACTIVE, 3, 10 + i, 10, 6, 6) for i in range(4)] + [(1, i, ACTIVE, 3, 10 + i, 10, 6, 6) for i in range(4)]
    for nb in (0, 4):
        mods = [(0, i, ACTIVE, 3, 10 + i, 10, 6, 6) for i in range(4)]
        if nb:
            mods += [(1, i, ACTIVE, 3, 10 + i, 10, 6, 6) for i in range(4)]
        for mode in (M_DEST_A, M_DEST_B, M_DEST_A | M_DEST_B, 0):
            for ab in ((0, 0), (1, 0), (2, 0), (1, 0x77), (3, 0x41)):
                calls = [Call(mode, ab[0], ab[1], mods), Call(), Call(mode, ab[0], ab[1]), Call()]
                cs.append(Case(4, nb, 255, 255, calls, f"cb-nb{nb}-m{mode}-ab{ab}"))
        for mode in (M_LOCKA, M_LOCKB, M_NULL, M_UNINIT):
            calls = [Call(0, 0, 0, mods), Call(mode, 0, 0), Call(), Call(mode, 0, 0, [(0, 0, FREE, 0, 0, 0, 0, 0)]), Call()]
            cs.append(Case(4, nb, 255, 255, calls, f"mode-nb{nb}-{mode:#x}"))
    return cs


def r_random(seed, n):
    rnd = random.Random(seed)
    P = [0, 1, 2, 3, 4, 5, 6, 8, 100, 101, 250, 251, 252, 253, 254, 255]
    S = [0, 1, 2, 3, 4, 5, 8, 254, 255]
    cs = []
    for ci in range(n):
        na = rnd.choice([1, 2, 3, 5, 8, 12, 20, 35])
        nb = rnd.choice([0, 0, 1, 3, 8, 12, 33])
        evcap = rnd.choice([0, 1, 2, 3, 5, 8, 255, 255])
        paircap = rnd.choice([0, 1, 2, 3, 5, 8, 255, 255])
        slots = [(0, i) for i in range(na)] + [(1, i) for i in range(nb)]
        calls = []
        for k in range(rnd.randint(2, 7)):
            mods = []
            for s in slots:
                if rnd.random() < (0.9 if k == 0 else 0.3):
                    st = rnd.choice([ACTIVE, ACTIVE, ACTIVE, ACTIVE, DISABLED, FREE, PENDING])
                    roles = rnd.choice([0, 1, 2, 3, 3, 1, 2, 4, 5, 0x81, 0x83, 0x87])
                    mods.append((s[0], s[1], st, roles, rnd.choice(P), rnd.choice(P), rnd.choice(S), rnd.choice(S)))
            mode = 0
            r = rnd.random()
            if r < 0.07: mode = M_LOCKA
            elif r < 0.1: mode = M_LOCKB
            elif r < 0.12: mode = M_NULL
            elif r < 0.14: mode = M_UNINIT
            elif r < 0.30: mode = rnd.choice([M_DEST_A, M_DEST_B, 3])
            ak = rnd.choice([0, 0, 0, 1, 2, 3])
            calls.append(Call(mode, ak, rnd.choice([0, 0x42]), mods))
        cs.append(Case(na, nb, evcap, paircap, calls, f"rnd{seed}-{ci}"))
    return cs


def r_perf():
    cs = []
    mods = [(0, i, ACTIVE, 1, i * 8, 0, 4, 4) for i in range(32)] + [(1, i, ACTIVE, 2, i * 8, 100, 4, 4) for i in range(32)]
    cs.append(Case(32, 32, 255, 255, [Call(0, 0, 0, mods)] + [Call() for _ in range(5)], "perf32-nohit"))
    mods = [(0, i, ACTIVE, 1, i * 8, 0, 4, 4) for i in range(32)] + [(1, i, ACTIVE, 2, i * 8 + 2, 2, 4, 4) for i in range(32)]
    cs.append(Case(32, 32, 255, 255, [Call(0, 0, 0, mods)] + [Call() for _ in range(5)], "perf32-hit32"))
    mods = [(0, i, ACTIVE, 1, i * 8, 0, 4, 4) for i in range(16)] + [(0, 16 + i, ACTIVE, 2, i * 8, 100, 4, 4) for i in range(16)]
    cs.append(Case(32, 0, 255, 255, [Call(0, 0, 0, mods)] + [Call() for _ in range(5)], "perf32single-nohit"))
    mods = [(0, 7 * i, ACTIVE, 1, i * 8, 0, 4, 4) for i in range(32)] + [(1, 7 * i, ACTIVE, 2, i * 8, 100, 4, 4) for i in range(32)]
    cs.append(Case(224, 224, 255, 255, [Call(0, 0, 0, mods)] + [Call() for _ in range(3)], "perf32in224-nohit"))
    return cs


def r_perf255():
    mods = [(0, i, ACTIVE, 3, i, 0, 1, 1) for i in range(255)]
    cs = [Case(255, 0, 255, 255, [Call(0, 0, 0, mods), Call()], "perf255single-nohit")]
    return cs


def r_perf255x():
    mods = [(0, i, ACTIVE, 1, i, 0, 1, 1) for i in range(255)] + [(1, i, ACTIVE, 2, i, 100, 1, 1) for i in range(255)]
    return [Case(255, 255, 255, 255, [Call(0, 0, 0, mods[:255]), Call(0, 0, 0, mods[255:]), Call()], "perf255two-nohit")]

def r_arith_small(axis):
    pos = [0, 1, 2, 127, 128, 250, 253, 254, 255]
    siz = [0, 1, 2, 3, 126, 127, 128, 254, 255]
    combos = [(p, s) for p in pos for s in siz]
    def xy(p, s):
        return (p, s, 10, 10) if axis == 0 else (10, 10, p, s)
    cases = []
    for g in range(0, 81, 9):
        for h in range(0, 81, 27):
            mods = []
            for i, (p, s) in enumerate(combos[g:g + 9]):
                x, w, y, hh = xy(p, s)
                mods.append((0, i, ACTIVE, 1, x, y, w, hh))
            for j, (p, s) in enumerate(combos[h:h + 27]):
                x, w, y, hh = xy(p, s)
                mods.append((1, j, ACTIVE, 2, x, y, w, hh))
            cases.append(Case(9, 27, 255, 255, [Call(0, 0, 0, mods)], f"arithS{axis}-{g}-{h}"))
    return cases

SUITES = {
    "arith0": lambda: r_arith(0), "arith1": lambda: r_arith(1),
    "big": r_big, "big2": r_big2, "single": r_single255, "dense": r_dense,
    "arithS0": lambda: r_arith_small(0), "arithS1": lambda: r_arith_small(1), "caps": r_caps, "cb": r_cb, "perf": r_perf, "perf255": r_perf255, "perf255x": r_perf255x,
    "rnd1": lambda: r_random(1, 150), "rnd2": lambda: r_random(2, 150), "rnd3": lambda: r_random(3, 150),
}

# ------------------------------------------------------------- emulator
API = "http://127.0.0.1:6128"


def get(path):
    with urllib.request.urlopen(API + path, timeout=10) as r:
        return json.load(r)


def post(path, data):
    rq = urllib.request.Request(API + path, data=json.dumps(data).encode(), method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(rq, timeout=10) as r:
        return json.load(r)


def ram(addr, n):
    return bytes.fromhex(get(f"/api/ram?addr={addr}&len={n}")["hex"])


def wram(addr, data):
    post("/api/ram", {"addr": addr, "data": data.hex()})


def sym(noi, name):
    return int(dict(re.findall(r"^DEF (\S+) 0x([0-9A-Fa-f]+)", Path(noi).read_text(), re.M))[name], 16)


def chunks(cases, limit=7800, loglimit=6000):
    cur, size, lsz = [], 1, 0
    for c in cases:
        sz = len(blob([c])) - 1
        ls = sum(len(r) for r in Model(c, 0, 0).run())
        if cur and (size + sz > limit or lsz + ls > loglimit):
            yield cur
            cur, size, lsz = [], 1, 0
        cur.append(c)
        size += sz
        lsz += ls
    if cur:
        yield cur


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument("suites", nargs="*")
    parser.add_argument("--emulator", type=Path, default=DEFAULT_EMULATOR)
    parser.add_argument("--list", action="store_true", help="print the suite names and exit")
    args = parser.parse_args()
    if args.list:
        print("\n".join(SUITES))
        return 0
    unknown = [name for name in args.suites if name not in SUITES]
    if unknown or not args.suites:
        parser.error(f"choose from: {', '.join(SUITES)}")
    global EMULATOR
    EMULATOR = args.emulator
    suites = args.suites
    noi = ROOT / ".build/ecsfuzz/obj/ecsfuzz.noi"
    dsk = ROOT / ".build/tests/GlasnostFWK-tests.dsk"
    s_status, s_go, s_cases = sym(noi, "ecsfuzz_status"), sym(noi, "ecsfuzz_go"), sym(noi, "cases")
    s_log, s_len = sym(noi, "ecsfuzz_log"), sym(noi, "ecsfuzz_log_length")
    ba, bb = sym(noi, "stor_a"), sym(noi, "stor_b")
    p = subprocess.Popen([str(EMULATOR), "--web-server", "--model", "6128", "--ram", "128", str(dsk)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    total_bad = 0
    try:
        t = time.time()
        while True:
            try:
                if get("/api/ping").get("ok"): break
            except OSError:
                pass
            time.sleep(0.5)
        time.sleep(6)
        post("/api/keytype", {"text": 'run"ECSFUZZ\n'})
        fc = sym(noi, "fwk_system_frame_count")
        t1 = time.time()
        while int.from_bytes(ram(fc, 2), "little") < 3:
            if time.time() - t1 > 180: raise RuntimeError("program never started")
            time.sleep(0.5)
        for suite in suites:
            cases = SUITES[suite]()
            nbad = 0
            for ch in chunks(cases):
                wram(s_status, b"\x00")
                while ram(s_status, 1)[0] != 0:
                    time.sleep(0.1)
                wram(s_cases, blob(ch))
                wram(s_go, b"\x01")
                t0 = time.time()
                while ram(s_status, 1)[0] == 0:
                    if time.time() - t0 > 600:
                        raise RuntimeError("timeout")
                    time.sleep(0.3)
                st = ram(s_status, 1)[0]
                n = int.from_bytes(ram(s_len, 2), "little")
                log = ram(s_log, n)
                recs = parse(log)
                if st != 0x5A:
                    print(f"[{suite}] harness status {st:#x} (log truncated)")
                exp = []
                models = []
                for c in ch:
                    m = Model(c, ba, bb)
                    r = m.run()
                    models.append(m)
                    exp += [(m, c, x) for x in r]
                for i, (m, c, x) in enumerate(exp):
                    if i >= len(recs):
                        print(f"[{suite}] missing record {i} ({c.name})")
                        nbad += 1
                        break
                    if recs[i][1:] != x[1:]:
                        nbad += 1
                        if nbad <= 40:
                            print(f"[{suite}] MISMATCH {c.name} call {x[1]}")
                            print("   expected:", describe(x, m)[:600])
                            print("   actual  :", describe(recs[i], m)[:600])
                        # records are positional; resync not needed
                tm = [r[0] for r in recs]
                print(f"[{suite}] frames/call (max): {max(tm) if tm else 0}")
                if suite.startswith("perf"):
                    k = 0
                    for c in ch:
                        print(f"   {c.name}: frames per call {tm[k:k+len(c.calls)]} events {[r[5] for r in recs[k:k+len(c.calls)]]}")
                        k += len(c.calls)
                print(f"[{suite}] chunk of {len(ch)} cases, {len(exp)} calls, log {n} bytes, {time.time()-t0:.1f}s")
            print(f"[{suite}] mismatching calls: {nbad}")
            total_bad += nbad
    finally:
        try: post("/api/quit", {})
        except Exception: pass
        try: p.wait(timeout=10)
        except subprocess.TimeoutExpired: os.killpg(p.pid, signal.SIGKILL)
    print("TOTAL mismatches", total_bad)
    return 1 if total_bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
