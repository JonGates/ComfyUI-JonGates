import itertools
import unittest

from test_cut import load_package


class ReferenceStyleTests(unittest.TestCase):
    def test_all_switch_combinations(self):
        node = load_package().NODE_CLASS_MAPPINGS["JonGatesReferenceStylePrompt"]()
        for scene, clothing, pose in itertools.product([False, True], repeat=3):
            with self.subTest(scene=scene, clothing=clothing, pose=pose):
                prompt, strength = node.build(scene, clothing, pose, "自然摄影", "暖色高光，青绿色阴影")
                self.assertEqual(strength, 0.0 if any((scene, clothing, pose)) else 1.0)
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
        prompt, strength = cls().build(False, False, False, "")
        self.assertEqual(strength, 1.0)
        self.assertIn("直接观察 <image2>", prompt)
        self.assertIn("发饰", prompt)
        self.assertIn("随身物品", prompt)

    def test_enabled_switches_request_edits_not_just_permission(self):
        node = load_package().NODE_CLASS_MAPPINGS["JonGatesReferenceStylePrompt"]()
        prompt, _ = node.build(True, True, True, "")
        for command in ("将图1的背景替换为图2的场景", "将图1人物的衣服更换为图2对应人物的衣服", "将图1人物的身体姿态、手臂动作及朝向调整为图2对应人物的姿势"):
            self.assertIn(command, prompt)
        self.assertNotIn("允许", prompt)


if __name__ == "__main__":
    unittest.main()
