import importlib.util
from pathlib import Path
import sys
import unittest

import torch

ROOT = Path(__file__).resolve().parents[1]


def load_package():
    spec = importlib.util.spec_from_file_location(
        "jongates_test_package", ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = package
    spec.loader.exec_module(package)
    return package


class CutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = load_package()
        cls.node = cls.package.NODE_CLASS_MAPPINGS["JonGatesCutQwenImage21"]
        cls.module = sys.modules[cls.node.__module__]

    def test_independent_registration_and_range(self):
        self.assertNotIn("CutQwenImage21", self.package.NODE_CLASS_MAPPINGS)
        schema = self.node.INPUT_TYPES()["required"]
        self.assertEqual(schema["resolution"][0], list(range(1024, 4097, 32)))
        self.assertEqual(schema["resolution"][1]["default"], 2048)
        self.assertEqual(self.node.RETURN_TYPES, ("IMAGE", "INT", "INT", "INT"))

    def test_all_high_resolution_sizes_remain_aligned(self):
        for res in range(1024, 4097, 32):
            for width, height in [(4672, 7008), (3840, 2160), (2048, 2048)]:
                with self.subTest(res=res, width=width, height=height):
                    (w, h), _ = self.module._pick_target_size(width, height, res, 0.8)
                    w, h = self.module._snap_fixed_point(w, h, res, 0.8, width, height)
                    self.assertEqual((w % 32, h % 32), (0, 0))
                    self.assertEqual(self.module._verify_fixed_point(w, h, res), (w, h))

    def test_known_portrait_dimensions(self):
        for resolution, expected in [(2048, (1664, 2496)), (4096, (3360, 5024))]:
            result, _ = self.module._pick_target_size(4672, 7008, resolution, 0.8)
            self.assertEqual(result, expected)

    def test_real_crop_and_pad_batch_preserve_inputs(self):
        image = torch.full((2, 48, 80, 3), 0.75)
        original = image.clone()
        for mode in ("crop", "pad"):
            result, w, h, res = self.node().run(image, 1024, 0.8, mode, 0.25)
            self.assertEqual(result.shape, (2, h, w, 3))
            self.assertEqual(res, 1024)
            self.assertTrue(torch.isfinite(result).all())
            self.assertTrue(torch.equal(image, original))
            self.assertAlmostEqual(result[0, h // 2, w // 2, 0].item(), 0.75, places=5)
            if mode == "pad":
                self.assertAlmostEqual(result[0, 0, 0, 0].item(), 0.25, places=5)

    def test_legacy_string_and_invalid_values(self):
        image = torch.zeros(1, 32, 32, 3)
        self.assertEqual(self.node().run(image, "1024", 0.8, "crop", 0)[3], 1024)
        for resolution in (512, 1000, 1050, 4128, 1024.5):
            with self.subTest(resolution=resolution), self.assertRaises(ValueError):
                self.node().run(image, resolution, 0.8, "crop", 0)
        with self.assertRaises(ValueError):
            self.node().run(image, 1024, 0.8, "invalid", 0)


if __name__ == "__main__":
    unittest.main()
