import unittest

import torch

from test_cut import load_package


class RotateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = load_package()
        cls.node = cls.package.NODE_CLASS_MAPPINGS["JonGatesRotateImage"]

    def test_namespace(self):
        self.assertNotIn("BlueBoxRotateImage", self.package.NODE_CLASS_MAPPINGS)
        self.assertEqual(self.node.RETURN_TYPES[1], "JONGATES_ROTATE_INFO")
        self.assertEqual(self.node.INPUT_TYPES()["optional"]["rotate_info"][0], "JONGATES_ROTATE_INFO")

    def test_right_angle_and_return_to_original(self):
        image = torch.zeros(1, 24, 40, 3)
        image[:, :12, :20, 0] = 1
        rotated, info = self.node().rotate(90, image)
        self.assertEqual(tuple(rotated.shape), (1, 40, 24, 3))
        restored, info = self.node().rotate(-90, rotated, info)
        self.assertEqual(tuple(restored.shape), tuple(image.shape))
        self.assertEqual(info["angle"], 0)
        self.assertTrue(torch.equal(restored, image))

    def test_fractional_rotation_is_finite(self):
        image = torch.ones(1, 24, 40, 3)
        rotated, info = self.node().rotate(15, image)
        self.assertTrue(torch.isfinite(rotated).all())
        self.assertEqual((info["orig_w"], info["orig_h"]), (40, 24))

    def test_explicit_errors_instead_of_silently_dropping_batch(self):
        with self.assertRaises(ValueError):
            self.node().rotate(0)
        with self.assertRaises(ValueError):
            self.node().rotate(0, torch.zeros(2, 24, 40, 3))
        with self.assertRaises(ValueError):
            self.node().rotate(0, torch.zeros(1, 24, 40, 3), {})


if __name__ == "__main__":
    unittest.main()
