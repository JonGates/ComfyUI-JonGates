import itertools
import unittest

from test_cut import load_package


class ReferenceStyleTests(unittest.TestCase):
    def test_all_switch_combinations(self):
        node = load_package().NODE_CLASS_MAPPINGS["JonGatesReferenceStylePrompt"]()
        for scene, clothing, pose in itertools.product([False, True], repeat=3):
            with self.subTest(scene=scene, clothing=clothing, pose=pose):
                prompt, = node.build(scene, clothing, pose, "自然摄影", "暖色高光，青绿色阴影")
                self.assertIn("<image1>", prompt)
                self.assertIn("<image2>", prompt)
                self.assertIn("暖色高光，青绿色阴影", prompt)
                self.assertIn("人物身份", prompt)
                for label, enabled in [("场景", scene), ("服饰", clothing), ("姿势", pose)]:
                    self.assertIn(label + ("可变：开启" if enabled else "可变：关闭"), prompt)
                    self.assertNotIn(label + ("可变：关闭" if enabled else "可变：开启"), prompt)

    def test_defaults_preserve_content_and_description_is_optional(self):
        cls = load_package().NODE_CLASS_MAPPINGS["JonGatesReferenceStylePrompt"]
        required = cls.INPUT_TYPES()["required"]
        for name in ("change_scene", "change_clothing", "change_pose"):
            self.assertFalse(required[name][1]["default"])
        prompt, = cls().build(False, False, False, "")
        self.assertIn("直接观察 <image2>", prompt)
        self.assertIn("发饰", prompt)
        self.assertIn("随身物品", prompt)


if __name__ == "__main__":
    unittest.main()
