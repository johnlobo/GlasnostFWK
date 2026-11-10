#!/usr/bin/env python3
"""Report linked code/data sizes without confusing sparse ABS examples with RAM."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

try:
    from tools.build.program_catalog import manifest_path, program_folder, program_folders, program_names
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, str(ROOT / "tools" / "build"))
    from program_catalog import manifest_path, program_folder, program_folders, program_names


def area_size(map_text: str, area: str) -> int:
    match = re.search(rf"^{re.escape(area)}\s+[0-9A-F]+\s+([0-9A-F]+)", map_text, re.MULTILINE)
    return int(match.group(1), 16) if match else 0


def main() -> int:
    rows = []
    for manifest in [manifest_path(folder) for folder in program_folders(ROOT)]:
        name = manifest.parent.name
        obj = ROOT / "build" / name / "obj"
        map_path = obj / f"{name}.map"
        bin_path = obj / f"{name}.bin"
        if not map_path.is_file() or not bin_path.is_file():
            raise SystemExit(f"build {name} first")
        text = map_path.read_text(errors="replace")
        kind = "Ejemplo" if manifest.parent.parent.name == "examples" else "Validación"
        rows.append((name, kind, area_size(text, "_CODE"), area_size(text, "_DATA"), bin_path.stat().st_size))
    out = [
        "# Tamaños de ejemplos y validaciones", "",
        "Generado desde los mapas del enlazador SDCC. El BIN puede incluir relleno por direcciones absolutas dispersas.", "",
        "| Programa | Tipo | Código enlazado | Datos enlazados | Bytes BIN |", "|---|---|---:|---:|---:|",
    ]
    out += [f"| {name} | {kind} | {code} | {data} | {binary} |" for name, kind, code, data, binary in rows]
    out += ["", "Este informe recoge tamaños; no ejecuta mediciones de ciclos ni de frecuencia de frames.", ""]
    destination = ROOT / "docs" / "design" / "build-sizes.md"
    destination.write_text("\n".join(out), encoding="utf-8")
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
