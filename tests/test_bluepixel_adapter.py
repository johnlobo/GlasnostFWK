"""Errores de transporte: el adaptador falla pronto y siempre recoge su proceso."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/glasnost"))
from bluepixel_adapter import BluePixel, BluePixelError


class TransportErrors(unittest.TestCase):
    def fake(self, body):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        script = Path(tmp.name) / "emulator"
        script.write_text(f"#!{sys.executable}\nimport json, sys, time\n" + body)
        script.chmod(0o755)
        return script

    def test_child_exit_reports_stderr(self):
        script = self.fake('sys.stderr.write("invalid ROM manifest\\n")\nsys.exit(2)\n')
        with self.assertRaisesRegex(BluePixelError, "invalid ROM manifest"):
            BluePixel(script, ROOT)

    def test_deadline_kills_an_unresponsive_child(self):
        script = self.fake('time.sleep(60)\n')
        with self.assertRaisesRegex(BluePixelError, "Tiempo agotado"):
            BluePixel(script, ROOT, timeout=0.05)

    def test_deadline_also_covers_a_blocked_pipe_write(self):
        capabilities = {"api_version": "1.3", "state_format": 1,
                        "roms_loaded": {"os": True, "basic": True, "amsdos": True}}
        script = self.fake('sys.stdin.readline()\nprint(json.dumps({"jsonrpc":"2.0", "id":1, "result":' + repr(capabilities) + '}), flush=True)\ntime.sleep(60)\n')
        with BluePixel(script, ROOT) as emu:
            emu.timeout = 0.2
            with self.assertRaisesRegex(BluePixelError, "Tiempo agotado"):
                emu.call("disc.load", {"data_base64": "A" * 500000})
            self.assertIsNotNone(emu.process.poll())

    def test_wrong_id_is_rejected(self):
        script = self.fake('sys.stdin.readline()\nprint(json.dumps({"jsonrpc":"2.0", "id":99, "result":{}}), flush=True)\n')
        with self.assertRaisesRegex(BluePixelError, "JSON-RPC inválida"):
            BluePixel(script, ROOT)

    def test_invalid_json_is_rejected(self):
        script = self.fake('sys.stdin.readline()\nprint("broken", flush=True)\n')
        with self.assertRaises(BluePixelError):
            BluePixel(script, ROOT)

    def test_incompatible_state_format_is_rejected(self):
        script = self.fake('sys.stdin.readline()\nprint(json.dumps({"jsonrpc":"2.0", "id":1, "result":{"api_version":"1.3", "state_format":99}}), flush=True)\n')
        with self.assertRaisesRegex(BluePixelError, "estado canónico 1"):
            BluePixel(script, ROOT)

    def test_context_collects_child_and_closed_session_rejects_requests(self):
        capabilities = {"api_version": "1.3", "state_format": 1,
                        "roms_loaded": {"os": True, "basic": True, "amsdos": True}}
        script = self.fake('for line in sys.stdin:\n request=json.loads(line)\n print(json.dumps({"jsonrpc":"2.0", "id":request["id"], "result":' + repr(capabilities) + '}), flush=True)\n')
        with BluePixel(script, ROOT) as emu:
            child = emu.process
            emu.stop()
        self.assertIsNotNone(child.poll())
        with self.assertRaisesRegex(BluePixelError, "cerrada"):
            emu.call("state.hash")
        emu.close()


if __name__ == "__main__":
    unittest.main()
