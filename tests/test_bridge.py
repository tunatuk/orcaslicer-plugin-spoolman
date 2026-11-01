import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


def load_plugin():
    orca = types.ModuleType("orca")
    orca.base = object
    orca.plugin = lambda cls: cls
    orca.register_capability = lambda cls: None
    orca.PluginResult = types.SimpleNamespace(RecoverableError="recoverable", FatalError="fatal")
    orca.ExecutionResult = types.SimpleNamespace(
        success=lambda message: ("success", message),
        skipped=lambda message: ("skipped", message),
        failure=lambda status, message: (status, message),
    )
    orca.slicing = types.ModuleType("orca.slicing")
    orca.slicing.SlicingPipelineCapabilityBase = object
    orca.slicing.psGCodePostProcess = 42
    orca.script = types.SimpleNamespace(ScriptPluginCapabilityBase=object)
    orca.pages = types.ModuleType("orca.pages")
    orca.pages.PagesPluginCapabilityBase = object
    orca.host = types.SimpleNamespace(ui=types.SimpleNamespace(WINDOW_MODAL=1))
    with patch.dict(sys.modules, {"orca": orca, "orca.pages": orca.pages,
                                  "orca.slicing": orca.slicing}):
        path = Path(__file__).parents[1] / "orcaslicer_plugin_spoolman" / "__init__.py"
        spec = importlib.util.spec_from_file_location("bridge_under_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module, orca


class BridgeTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).parents[1] / ".tmp"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.bridge, self.orca = load_plugin()
        self.bridge.PLUGIN_DIR = self.temp.name
        self.bridge.SETTINGS_FILE = os.path.join(self.temp.name, "settings.json")
        self.bridge.PENDING_FILE = os.path.join(self.temp.name, "pending.json")
        self.bridge.LOG_FILE = os.path.join(self.temp.name, "bridge.log")
        with open(self.bridge.SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"spoolman_url": "http://spoolman.local:7912", "first_run": False}, f)

    def test_settings_uses_available_modal_api(self):
        calls = []
        self.orca.host.ui.create_window = lambda **kwargs: calls.append(kwargs)
        self.bridge.show_tutorial_dialog()
        self.assertEqual(calls[0]["style"], 1)
        self.assertIn("on_submit", calls[0])
        calls[0]["on_submit"]({"url": "http://spoolman.local:7912/"})
        self.assertEqual(self.bridge.get_settings()["spoolman_url"],
                         "http://spoolman.local:7912")

    def test_spoolman_page_exposes_actions_and_dispatches_them(self):
        page = self.bridge.SpoolmanPage()
        html = page.get_ui()
        for action in ("settings", "sync", "usage"):
            self.assertIn(f"run('{action}')", html)
        messages = []
        page.post_message = messages.append
        with patch.object(self.bridge.SpoolmanConfigScript, "execute") as settings, \
             patch.object(self.bridge.SpoolmanSyncScript, "execute") as sync, \
             patch.object(self.bridge.SpoolmanApplyUsageScript, "execute") as usage:
            page.on_message({"action": "settings"})
            page.on_message({"action": "sync"})
            page.on_message({"action": "usage"})
            settings.assert_called_once_with()
            sync.assert_called_once_with()
            usage.assert_called_once_with()
        self.assertEqual(messages[-1]["text"], "0 pending usage records.")
        page.on_message({"action": "unknown"})
        self.assertEqual(len(messages), 3)

    def test_single_filament_queues_then_confirms_usage(self):
        gcode = os.path.join(self.temp.name, "job.gcode")
        with open(gcode, "w", encoding="utf-8") as f:
            f.write("; filament used [g] = 12.5\n; filament_settings_id = PLA (#12) - Spoolman\n")
        spool = {"id": 12, "filament": {"name": "PLA", "vendor": {"name": "Example"}}}

        class Response:
            status_code = 200

            def json(self):
                return [spool]

            def raise_for_status(self):
                pass

        ui_calls = []
        self.orca.host.ui.message = lambda *args, **kwargs: ui_calls.append(args) or "yes"
        context = types.SimpleNamespace(step=42, gcode_path=gcode, output_name="job")
        with patch.object(self.bridge.requests, "get", return_value=Response()), \
             patch.object(self.bridge.requests, "put", return_value=Response()) as put:
            self.assertEqual(self.bridge.SpoolmanGCode().execute(context)[0], "success")
            self.assertEqual(len(self.bridge.read_pending_usage()), 1)
            self.assertFalse(ui_calls, "slicing worker must not call host UI")
            self.assertEqual(self.bridge.SpoolmanApplyUsageScript().execute()[0], "success")
            self.assertEqual(self.bridge.read_pending_usage(), [])
            put.assert_called_once_with("http://spoolman.local:7912/api/v1/spool/12/use",
                                        json={"use_weight": 12.5}, timeout=10)

    def test_multifilament_job_is_not_queued(self):
        gcode = os.path.join(self.temp.name, "multi.gcode")
        with open(gcode, "w", encoding="utf-8") as f:
            f.write("; filament used [g] = 12.5, 8.0\n")
        context = types.SimpleNamespace(step=42, gcode_path=gcode, output_name="multi")
        result = self.bridge.SpoolmanGCode().execute(context)
        self.assertEqual(result[0], "skipped")
        self.assertEqual(self.bridge.read_pending_usage(), [])

    def test_uncertain_usage_request_is_not_retried(self):
        self.bridge.write_pending_usage([{"job_key": "job-1", "spool_id": 12,
                                          "spool_desc": "Example PLA", "used_g": 12.5}])
        answers = iter(["yes", "no"])
        self.orca.host.ui.message = lambda *args, **kwargs: next(answers)
        with patch.object(self.bridge.requests, "put", side_effect=TimeoutError("timed out")) as put:
            self.assertEqual(self.bridge.SpoolmanApplyUsageScript().execute()[0], "recoverable")
            self.assertEqual(self.bridge.read_pending_usage()[0]["state"], "sending")
            self.assertEqual(self.bridge.SpoolmanApplyUsageScript().execute()[0], "skipped")
            put.assert_called_once()

    def test_field_sync_does_not_delete_existing_fields(self):
        class Response:
            status_code = 200

            def json(self):
                return [{"key": "compatible_printers"}, {"key": "max_volumetric_speed"}]

        with patch.object(self.bridge.requests, "get", return_value=Response()), \
             patch.object(self.bridge.requests, "delete") as delete, \
             patch.object(self.bridge.requests, "post") as post:
            self.bridge.ensure_spoolman_fields(dry_run=False)
            delete.assert_not_called()
            post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
