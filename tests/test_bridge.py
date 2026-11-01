import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image
import torch

from test_cut import load_package, ROOT


class ExecutionBlocker:
    def __init__(self, message):
        self.message = message


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        package = load_package()
        cls.node = package.NODE_CLASS_MAPPINGS["JonGatesBridge"]
        cls.module = sys.modules[cls.node.__module__]
        cls.core = cls.module.core

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.paths = types.SimpleNamespace(get_temp_directory=lambda: self.tmp.name)
        self.mock = patch.dict(sys.modules, {
            "folder_paths": self.paths,
            "comfy_execution.graph": types.SimpleNamespace(ExecutionBlocker=ExecutionBlocker),
        })
        self.mock.start()
        self.addCleanup(self.mock.stop)
        self.core.clear_bridge("17")
        self.image = torch.full((1, 16, 24, 3), 0.5)

    def test_never_outputs_image_mask_and_preview(self):
        result = self.node().doit(self.image, unique_id="17")
        image, mask = result["result"]
        self.assertEqual(tuple(image.shape), (1, 16, 24, 3))
        self.assertEqual(tuple(mask.shape), (1, 16, 24))
        self.assertEqual(mask.sum().item(), 0)
        preview = result["ui"]["images"][0]
        self.assertEqual(preview["subfolder"], "JonGatesBridge")
        self.assertTrue((Path(self.tmp.name) / preview["subfolder"] / preview["filename"]).is_file())

    def test_block_preview_continue_then_block_again(self):
        node = self.node()
        first = node.doit(self.image, block=True, unique_id="17")
        self.assertIsInstance(first["result"][0], ExecutionBlocker)
        self.assertTrue(first["ui"]["images"])
        before = node.IS_CHANGED(self.image, block=True, unique_id="17")
        self.core.set_bridge_continued("17")
        after = node.IS_CHANGED(self.image, block=True, unique_id="17")
        self.assertNotEqual(before, after)
        self.assertIsInstance(node.doit(self.image, block=True, unique_id="17")["result"][0], torch.Tensor)
        self.assertIsInstance(node.doit(self.image, block=True, unique_id="17")["result"][0], ExecutionBlocker)

    def test_editor_result_and_mask_only_used_on_continue(self):
        image_path = Path(self.tmp.name) / "edited.png"
        mask_path = Path(self.tmp.name) / "mask.png"
        Image.new("RGB", (24, 16), "red").save(image_path)
        Image.new("L", (24, 16), 255).save(mask_path)
        self.core.set_bridge_image("17", str(image_path), str(mask_path), None)
        self.core.set_bridge_continued("17")
        edited, mask = self.node().doit(self.image, unique_id="17")["result"]
        self.assertEqual(edited[0, 0, 0].tolist(), [1, 0, 0])
        self.assertTrue(torch.all(mask == 1))
        fresh, mask = self.node().doit(self.image, unique_id="17")["result"]
        self.assertNotEqual(fresh[0, 0, 0].tolist(), [1, 0, 0])
        self.assertEqual(mask.sum().item(), 0)

    def test_reference_does_not_change_output_and_is_cleared(self):
        result = self.node().doit(self.image, unique_id="17", reference=torch.ones_like(self.image))
        self.assertEqual(result["ui"]["reference_present"], [True])
        self.assertIsNotNone(self.core.get_bridge_reference("17"))
        self.assertLess(result["result"][0].max().item(), 1)
        self.node().doit(self.image, unique_id="17")
        self.assertIsNone(self.core.get_bridge_reference("17"))

    def test_cache_invalidation_accepts_reference_input(self):
        self.node.IS_CHANGED(self.image, unique_id="17", reference=self.image)

    def test_frontend_is_independent_and_bridge_only(self):
        js = (ROOT / "web/jongates_bridge.js").read_text(encoding="utf-8")
        html = (ROOT / "web/mask-editor.html").read_text(encoding="utf-8")
        self.assertIn('nodeData.name !== "JonGatesBridge"', js)
        for old in ("/bluebox/", "/extensions/ComfyUI-BlueBox", 'dbName: "MaskEditorDB"', '"mask_saved"'):
            self.assertNotIn(old, js + html)
        self.assertNotIn("native_seed_fix", js)
        self.assertIn("JonGatesMaskEditorDB", js)
        self.assertIn("JonGatesMaskEditorDB", html)


if __name__ == "__main__":
    unittest.main()
