# SPDX-License-Identifier: MIT
# Copyright (c) 2026 JonGates

import math
import json


class JonGatesReferenceEditPlan:
    """Select structured reference fields before composing editing instructions."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "reference_description": ("STRING", {"forceInput": True}),
                "change_scene": ("BOOLEAN", {"default": True, "label_on": "替换场景", "label_off": "保留场景"}),
                "change_clothing": ("BOOLEAN", {"default": False, "label_on": "更换服装", "label_off": "保留服装"}),
                "change_pose": ("BOOLEAN", {"default": True, "label_on": "参考骨架", "label_off": "保留原姿势"}),
                "pose_strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05}),
                "extra_instruction": ("STRING", {"default": "自然摄影质感，保留原图人物身份、发饰及随身物品。", "multiline": True}),
            }
        }

    RETURN_TYPES = ("STRING", "FLOAT")
    RETURN_NAMES = ("prompt", "pose_strength")
    FUNCTION = "build"
    CATEGORY = "JonGates/Qwen"
    DESCRIPTION = "接双图结构化分析JSON。只将开关允许的参考字段送入提示词，避免关闭服装后仍泄露参考衣服。姿势强度输出需连接Qwen Union ControlNet。"

    def build(self, reference_description, change_scene, change_clothing, change_pose, pose_strength, extra_instruction):
        if not reference_description.strip():
            raise ValueError("参考图描述为空，请检查PE反推输出。")
        try:
            data = json.loads(reference_description)
            keys = ('source_identity','source_clothing','source_items','source_scene','source_pose',
                    'reference_scene','reference_clothing','reference_pose','reference_style')
            if not isinstance(data, dict) or any(not isinstance(data.get(k), str) or not data[k].strip() for k in keys):
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError("需要双图结构化分析节点输出的完整JSON，不能直接输入PE自由描述。") from None
        strength = float(pose_strength)
        if not math.isfinite(strength) or not 0 <= strength <= 2:
            raise ValueError("姿态强度必须是0到2之间的有限数值。")
        parts = [
            "编辑唯一输入照片中的原人物。参考照片已经转写成下方描述，它只提供素材，不是要求照搬的整张成片。"
            "人物身份、面部五官、脸型、发型、发饰和随身物品都来自输入的原照片，不采用参考描述中另一个人的长相。",
            "原人物身份与发型：" + data['source_identity'] + "。必须保留的原图饰品及随身物品：" + data['source_items'],
            "【必须执行的编辑要求，优先于参考内容描述】",
            "替换原图背景：移除原照片的旧环境，将背景重新生成为：" + data['reference_scene'] + "。"
            "包含与动作有关的栏杆、座椅等环境支撑，合理安排透视及人物落位。必须有实际的场景变化，不只是给旧背景调色。"
            if change_scene else
            "保留原图场景：" + data['source_scene'] + "。保留原背景物体、布局、空间和透视，只改变光照与色彩。",
            "更换原图衣服：" + data['reference_clothing'] + "。采用这些款式、剪裁、面料与纹样；不要换脸、发型、头饰或随身物品。"
            if change_clothing else
            "保留原图衣服：" + data['source_clothing'] + "。保持原衣服款式、剪裁、面料、纹样与原有配色关系，不换装。",
            "必须改变身体姿势：" + data['reference_pose'] + "。严格依据提供的姿态骨架重新安排人物的身体、肩膀、肘部、手腕与头部位置，"
            "同时参考上述动作描述。不要沿用原照片动作。允许身体朝向和画面位置随目标骨架变化，保持同一人物身份与合理解剖。"
            if change_pose else
            "保留原图姿势：" + data['source_pose'] + "。保留原身体动作、手势、头部朝向、人物位置与比例。",
            "原照片中真实存在的帽子、发饰、包、首饰、花束和手持物必须保留，不引入参考人物的随身物品。"
            "换姿势时让原有手持物仍在画面里自然持握，不能直接删除。"
            "采用这些摄影色调与光线：" + data['reference_style'] + "。保持自然肤色和真实摄影质感。"
            "仅输出一张编辑后的摄影图，不输出骨架、拼图或新增文字。",
        ]
        if extra_instruction.strip():
            parts.append("补充细节（不得覆盖以上开关要求）：" + extra_instruction.strip())
        return "\n\n".join(parts), strength if change_pose else 0.0


NODE_CLASS_MAPPINGS = {"JonGatesReferenceEditPlan": JonGatesReferenceEditPlan}
NODE_DISPLAY_NAME_MAPPINGS = {"JonGatesReferenceEditPlan": "参考编辑计划与姿态强度 (JonGates)"}
