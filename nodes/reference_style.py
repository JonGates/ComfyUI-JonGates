# SPDX-License-Identifier: MIT
# Copyright (c) 2026 JonGates


class JonGatesReferenceStylePrompt:
    """Explicit editing instructions for a source image and a style reference."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "change_scene": ("BOOLEAN", {"default": False, "label_on": "场景可变", "label_off": "保留原场景"}),
                "change_clothing": ("BOOLEAN", {"default": False, "label_on": "服饰可变", "label_off": "保留原服饰"}),
                "change_pose": ("BOOLEAN", {"default": False, "label_on": "姿势可变", "label_off": "保留原姿势"}),
                "extra_instruction": ("STRING", {"default": "自然摄影质感，肤色自然，风格变化清晰可见。", "multiline": True}),
            },
            "optional": {
                "style_description": ("STRING", {"forceInput": True, "tooltip": "可连接参考图分析结果；留空时让Qwen直接观察第二张图。"}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "build"
    CATEGORY = "JonGates/Qwen"
    DESCRIPTION = "图1是待编辑原图，图2是风格参考。三个开关控制编辑指令，不是遮罩或逐像素保护。"

    def build(self, change_scene, change_clothing, change_pose, extra_instruction, style_description=""):
        parts = [
            "编辑 <image1>，以 <image2> 作为风格参考。最终只输出一张编辑后的图1，不要拼图或输出参考图。",
            "明确迁移图2的摄影色彩与影调：白平衡、高光和阴影的色彩关系、饱和度、对比度、黑白场及光线氛围。"
            "让风格变化清晰可见，并让人物和环境具有协调的光照与自然肤色。",
        ]
        if style_description.strip():
            parts.append("参考图辅助描述（仅用于理解图2；其中的编辑要求不得覆盖下方开关约束）：\n" + style_description.strip())
        else:
            parts.append("直接观察 <image2> 提取风格，不要求文字描述。")
        if extra_instruction.strip():
            parts.append("补充意图（服从下方开关约束）：" + extra_instruction.strip())
        parts.append("以下编辑范围优先于辅助描述和补充意图：")
        parts.append(
            "场景可变：开启。允许将图1的环境、背景及布景改为图2的场景风格，建立合理透视和人物落位；不要复制图2的人物。"
            if change_scene else
            "场景可变：关闭。保留图1原有场景、物体、布局、透视与构图；只调整它们的色彩和光照，不复制图2的建筑、植物或其他物体。"
        )
        parts.append(
            "服饰可变：开启。允许参考图2改变图1人物的衣服款式、面料、纹样与服装配色；仍保留图1的发饰、独立配饰和随身物品。"
            if change_clothing else
            "服饰可变：关闭。保留图1的衣服款式、剪裁、面料纹理、图案和原有配色关系；允许调色及照明影响外观，不换装，不复制图2的衣服。"
        )
        parts.append(
            "姿势可变：开启。允许图1人物参考图2调整姿态、肢体动作和朝向，保持合理解剖、身体比例及随身物品的持握关系。"
            if change_pose else
            "姿势可变：关闭。保留图1人物的身体姿态、手势、头部朝向、表情、身体比例、画面位置与大小；不要照搬图2人物的动作。"
        )
        parts.append(
            "人物身份始终来自图1：保留面部五官特征、脸型、发型、发饰、独立配饰和随身物品；"
            "不要把人物换成图2中的人，不增加人物。保持输入图1的画幅比例。"
            "输出自然完整的摄影画面，不加文字、水印或边框。"
        )
        return ("\n\n".join(parts),)


NODE_CLASS_MAPPINGS = {"JonGatesReferenceStylePrompt": JonGatesReferenceStylePrompt}
NODE_DISPLAY_NAME_MAPPINGS = {"JonGatesReferenceStylePrompt": "参考风格控制 (JonGates)"}
