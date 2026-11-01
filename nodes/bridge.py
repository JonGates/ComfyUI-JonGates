# SPDX-License-Identifier: MIT
# Adapted from ComfyUI-BlueBox, Copyright (c) 2026 zhoutingxi.
# Modifications Copyright (c) 2026 JonGates. See THIRD_PARTY_NOTICES.md.

import os
import uuid
import numpy as np
import torch
from PIL import Image, ImageOps
from ..resources import bridge_state as core


def _paths():
    import folder_paths
    return folder_paths


class JonGatesBridge:
    """
    Bridge(JonGates)：工作流中间用。

    语义：
      - 点"继续"  → 用编辑器烘焙图（磁盘缓存）作为输出。
      - 点"运行"  → 无论上游变没变，一律重新注入上游原图，走占位刷新流程。

    optional.reference：仅用于编辑器"对比参考图"，不参与主输出、不影响 block。
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
            },
            "optional": {
                "block": ("BOOLEAN", {
                    "default": False,
                    "label_on": "if_not_continued",
                    "label_off": "never",
                    "tooltip": (
                        "if_not_continued：未点\"继续\"前，执行到此停住，下游不执行。\n"
                        "never：从不停止，直接放行。"
                    ),
                }),
                "reference": ("IMAGE",),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "mask")
    FUNCTION = "doit"
    OUTPUT_NODE = True
    CATEGORY = "JonGates"

    def doit(self, image, block=False, unique_id=None, reference=None):
        node_id = str(unique_id)
        if image.ndim != 4 or image.shape[0] != 1 or image.shape[-1] < 3:
            raise ValueError("JonGates Bridge currently requires a single RGB/RGBA image")

        core.set_bridge_reference(node_id, None)
        if reference is not None:
            try:
                ref_img = reference[0].cpu().numpy()
                if ref_img.ndim == 3 and ref_img.shape[-1] >= 3:
                    ref_img = ref_img[..., :3]
                ref_u8 = np.clip(ref_img * 255, 0, 255).astype(np.uint8)
                ref_pil = Image.fromarray(ref_u8, mode="RGB")
                temp_dir = _paths().get_temp_directory()
                sub_dir = os.path.join(temp_dir, "JonGatesBridge")
                os.makedirs(sub_dir, exist_ok=True)
                ref_fname = "jg_ref_{}_{}.png".format(node_id, uuid.uuid4().hex[:8])
                ref_fpath = os.path.join(sub_dir, ref_fname)
                ref_pil.save(ref_fpath)
                core.set_bridge_reference(node_id, ref_fpath)
            except Exception as e:
                print("[JonGates] 参考图保存失败:", e)

        continued = core.consume_bridge_continued(node_id)

        if continued:
            image_path, mask_path, preview_item = core.get_bridge_paths(node_id)
            print(
                f"[JonGates] Bridge 继续: node_id={node_id}, "
                f"image_path={image_path}, mask_path={mask_path}"
            )
            if image_path and os.path.isfile(image_path):
                pixels, mask = self._load_from_disk(image_path, mask_path)

                ui_preview = [preview_item] if preview_item else [{
                    "filename": os.path.basename(image_path),
                    "subfolder": "",
                    "type": "input",
                }]

                return self._finalize(
                    node_id, ui_preview, pixels, mask, block, continued,
                    reference=reference,
                )

            print(f"[JonGates] Bridge 收到继续标记但无烘焙图，回退重新注入")

        img = image[0].cpu().numpy()
        if img.ndim == 3 and img.shape[-1] >= 3:
            img = img[..., :3]
        rgb_np_u8 = np.clip(img * 255, 0, 255).astype(np.uint8)
        pil = Image.fromarray(rgb_np_u8, mode="RGB")

        temp_dir = _paths().get_temp_directory()
        sub_dir = os.path.join(temp_dir, "JonGatesBridge")
        os.makedirs(sub_dir, exist_ok=True)
        fname = "jg_bridge_{}_{}.png".format(node_id, uuid.uuid4().hex[:8])
        fpath = os.path.join(sub_dir, fname)
        pil.save(fpath)

        core.set_bridge_image(node_id, fpath, None, {
            "filename": fname,
            "subfolder": "JonGatesBridge",
            "type": "temp",
        })

        h, w = rgb_np_u8.shape[:2]
        mask = torch.zeros((1, h, w), dtype=torch.float32)
        image_tensor = torch.from_numpy(
            (rgb_np_u8.astype(np.float32) / 255.0)
        )[None,]

        ui_preview = [{
            "filename": fname,
            "subfolder": "JonGatesBridge",
            "type": "temp",
        }]

        return self._finalize(
            node_id, ui_preview, image_tensor, mask, block, continued,
            reference=reference,
        )

    def _finalize(self, node_id, images_ui, pixels, mask, block, continued,
                  reference=None):
        ui = {"images": images_ui}
        if reference is not None:
            ui["reference_present"] = [True]

        should_block = False
        if block and not continued:
            should_block = True

        if should_block:
            try:
                from comfy_execution.graph import ExecutionBlocker
                return {
                    "ui": ui,
                    "result": (ExecutionBlocker(None), ExecutionBlocker(None)),
                }
            except Exception as e:
                print(f"[JonGates] ExecutionBlocker 不可用（{e}），block 被忽略")
                return {
                    "ui": ui,
                    "result": (pixels, mask),
                }

        return {
            "ui": ui,
            "result": (pixels, mask),
        }

    def _load_from_disk(self, image_path, mask_path):
        i = Image.open(image_path)
        i = ImageOps.exif_transpose(i)
        rgb = i.convert("RGB")
        rgb_np = np.array(rgb).astype(np.float32) / 255.0
        image_tensor = torch.from_numpy(rgb_np)[None,]

        rgb_h, rgb_w = rgb_np.shape[:2]

        mask_np = None
        if mask_path and os.path.isfile(mask_path):
            try:
                m = Image.open(mask_path).convert("L")
                mask_np = np.array(m).astype(np.float32) / 255.0
            except Exception as e:
                print(f"[JonGates] 读取遮罩失败：{e}")
                mask_np = None

        if mask_np is not None and (mask_np.shape[0] != rgb_h or mask_np.shape[1] != rgb_w):
            print(f"[JonGates] 遮罩尺寸 {mask_np.shape} 与主图 {(rgb_h, rgb_w)} 不匹配，回退全零")
            mask_np = None
        if mask_np is None:
            mask_np = np.zeros((rgb_h, rgb_w), dtype=np.float32)

        mask_tensor = torch.from_numpy(mask_np)[None,]
        return image_tensor, mask_tensor

    @classmethod
    def IS_CHANGED(cls, image, block=False, unique_id=None, reference=None):
        node_id = str(unique_id) if unique_id else ""
        seq = core.get_bridge_continue_seq(node_id)
        block_flag = 1 if block else 0
        return f"{seq}_{block_flag}"



NODE_CLASS_MAPPINGS = {"JonGatesBridge": JonGatesBridge}
NODE_DISPLAY_NAME_MAPPINGS = {"JonGatesBridge": "Bridge (JonGates)"}
