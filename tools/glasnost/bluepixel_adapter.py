"""Adaptador síncrono de BluePixel CPCApi 1.x para pruebas sin ventana (stdlib).

Cada instancia posee un proceso stdio privado; no usa puertos ni duerme entre
fotogramas. El llamador serializa las llamadas y cierra la sesión con ``with``.
"""
from __future__ import annotations

import base64
import json
import queue
import subprocess
import tempfile
import threading
import time
from collections import defaultdict
from pathlib import Path


class BluePixelError(RuntimeError):
    pass


class BluePixel:
    capabilities = frozenset({"headless", "run", "capture", "memory", "input", "state", "stop"})

    def __init__(self, binary: Path, rom_dir: Path, *, timeout: float = 30):
        self.timeout = timeout
        self.frames = 0
        self.method_seconds = defaultdict(float)
        self._id = 0
        self._closed = False
        self._replies = queue.Queue()
        self._writer = None
        self._stderr = tempfile.TemporaryFile(mode="w+t")
        try:
            self.process = subprocess.Popen(
                [str(binary.resolve()), "--rom-dir", str(rom_dir.resolve())],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._stderr,
                text=True, encoding="utf-8", bufsize=1,
            )
        except BaseException:
            self._stderr.close()
            raise
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        try:
            self.session = self.call("session.capabilities")
            if not self.session.get("api_version", "").startswith("1.") or self.session.get("state_format") != 1:
                raise BluePixelError("BluePixel requiere CPCApi 1.x y estado canónico 1")
            if not all(self.session.get("roms_loaded", {}).get(role) for role in ("os", "basic", "amsdos")):
                raise BluePixelError("Faltan ROMs CPC 6128 en la sesión BluePixel")
        except BaseException:
            self.close()
            raise

    def _read(self):
        try:
            for line in self.process.stdout:
                self._replies.put(line)
        finally:
            self._replies.put(None)

    def call(self, method: str, params: dict | None = None):
        if self._closed:
            raise BluePixelError("La sesión BluePixel está cerrada")
        self._id += 1
        started = time.perf_counter()
        try:
            request = json.dumps({"jsonrpc": "2.0", "id": self._id,
                                  "method": method, "params": params or {}}) + "\n"
            if len(request.encode("utf-8")) > 1024 * 1024:
                raise BluePixelError(f"Petición demasiado grande en {method}")
            # Include blocked pipe writes in the request deadline as well as reads.
            def send():
                try:
                    self.process.stdin.write(request)
                    self.process.stdin.flush()
                except (OSError, ValueError) as error:
                    self._replies.put(error)
            self._writer = threading.Thread(target=send, daemon=True)
            self._writer.start()
            try:
                line = self._replies.get(timeout=self.timeout)
            except queue.Empty as error:
                raise BluePixelError(f"Tiempo agotado en {method}") from error
            if isinstance(line, Exception):
                raise BluePixelError(f"{method}: {line}")
            self._writer.join(timeout=self.timeout)
            if line is None:
                self.process.wait(timeout=2)
                self._stderr.seek(0)
                raise BluePixelError(f"BluePixel terminó durante {method}: {self._stderr.read().strip()}")
            reply = json.loads(line)
            if reply.get("jsonrpc") != "2.0" or reply.get("id") != self._id:
                raise BluePixelError(f"Respuesta JSON-RPC inválida en {method}")
            if "error" in reply:
                raise BluePixelError(f"{method}: {reply['error']}")
            return reply["result"]
        except (OSError, ValueError, KeyError, BluePixelError) as error:
            # After a timeout/protocol error the stream cannot safely be reused.
            self.close()
            if isinstance(error, BluePixelError):
                raise
            raise BluePixelError(f"{method}: {error}") from error
        finally:
            self.method_seconds[method] += time.perf_counter() - started

    def run(self, frames: int):
        result = self.call("run.frames", {"count": frames})
        self.frames += result["ran"]
        if result["ran"] != frames:
            raise BluePixelError(f"Ejecución interrumpida: {result}")
        return result

    def read(self, address: int | str, length: int = 1) -> bytes:
        return bytes.fromhex(self.call("mem.read", {"address": address, "length": length})["hex"])

    def write(self, address: int | str, value: int):
        return self.call("mem.write", {"address": address, "value": value})

    def key(self, row: int, mask: int, pressed: bool):
        self.call("input.matrix", {"row": row, "mask": mask, "pressed": pressed})

    def load(self, disk: Path, symbols: Path):
        self.call("disc.load", {"drive": 0, "name": disk.name, "data_base64": base64.b64encode(disk.read_bytes()).decode()})
        self.call("symbols.load", {"data_base64": base64.b64encode(symbols.read_bytes()).decode()})
        self.call("machine.reset")

    def boot(self, command: str, ready_address: int | str, ready_value: int, *, limit: int = 3000):
        self.run(150)
        self.call("input.text", {"text": command + "\n"})
        for _ in range(0, limit, 10):
            self.run(10)
            if self.read(ready_address)[0] == ready_value:
                return
        raise BluePixelError(f"El juego no está preparado tras {limit} fotogramas")

    def capture(self):
        return self.call("screen.capture", {"metadata": True})

    def save(self) -> bytes:
        return base64.b64decode(self.call("state.save")["data_base64"], validate=True)

    def restore(self, state: bytes):
        result = self.call("state.restore", {"data_base64": base64.b64encode(state).decode()})
        if result != {"restored": True, "hazards": 0}:
            self.close()
            raise BluePixelError(f"Estado incompatible con ROMs o medios actuales: {result}")

    def state_hash(self) -> str:
        return self.call("state.hash")["hash"]

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._writer is not None and self._writer.is_alive():
            # Closing a pipe while another thread owns its write lock can deadlock.
            self.process.terminate()
            self._writer.join(timeout=2)
            if self._writer.is_alive():
                self.process.kill()
                self._writer.join(timeout=2)
        try:
            self.process.stdin.close()
        except OSError:
            pass
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        self._reader.join(timeout=2)
        self.process.stdout.close()
        self._stderr.close()

    def stop(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
