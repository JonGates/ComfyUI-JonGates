import importlib.util
import itertools
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('reference_edit_plan', Path(__file__).parents[1]/'nodes/reference_edit_plan.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReferenceEditPlanTests(unittest.TestCase):
    analysis = json.dumps({'source_identity':'原人物黑发', 'source_clothing':'条纹裙', 'source_items':'草帽花束猫包', 'source_scene':'车站', 'source_pose':'抬手扶帽', 'reference_scene':'绿草栏杆', 'reference_clothing':'水手服', 'reference_pose':'侧身搭栏杆', 'reference_style':'暖光低饱和'}, ensure_ascii=False)
    def test_switches_are_independent_and_drive_real_pose_strength(self):
        node = module.JonGatesReferenceEditPlan()
        for scene, clothing, pose in itertools.product([False, True], repeat=3):
            prompt, strength = node.build(self.analysis, scene, clothing, pose, 0.8, '')
            self.assertEqual(strength, 0.8 if pose else 0.0)
            self.assertIn('替换原图背景' if scene else '保留原图场景', prompt)
            self.assertIn('更换原图衣服' if clothing else '保留原图衣服', prompt)
            self.assertIn('必须改变身体姿势' if pose else '保留原图姿势', prompt)
            self.assertNotIn('保留原图姿势' if pose else '必须改变身体姿势', prompt)
            self.assertIn('唯一输入照片', prompt)
            self.assertNotIn('<image2>', prompt)
            self.assertEqual('水手服' in prompt, clothing)
            self.assertEqual('绿草栏杆' in prompt, scene)
            self.assertEqual('侧身搭栏杆' in prompt, pose)
            self.assertIn('草帽花束猫包', prompt)

    def test_empty_caption_fails_instead_of_silently_doing_nothing(self):
        with self.assertRaisesRegex(ValueError, '参考图描述'):
            module.JonGatesReferenceEditPlan().build('  ', True, False, True, 1.0, '')

    def test_invalid_strength_is_rejected(self):
        for strength in [float('nan'), float('inf'), -1, 4]:
            with self.assertRaises(ValueError):
                module.JonGatesReferenceEditPlan().build(self.analysis, True, False, True, strength, '')

    def test_unstructured_caption_cannot_leak_reference_clothing(self):
        with self.assertRaisesRegex(ValueError, 'JSON'):
            module.JonGatesReferenceEditPlan().build('她身穿水手服，右上角有水印', True, False, True, 1.0, '')


if __name__ == '__main__':
    unittest.main()
