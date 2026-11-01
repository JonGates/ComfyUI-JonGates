# ComfyUI-JonGates

JonGates 的 ComfyUI 图像工具节点。独立安装、独立节点 ID，不依赖 BlueBox 或 Goohaitools。

## 安装与更新

在 ComfyUI 的 `custom_nodes` 目录运行：

```shell
git clone https://github.com/JonGates/ComfyUI-JonGates.git
```

重启 ComfyUI 并刷新网页，在节点搜索中输入 `JonGates`。
PyTorch、NumPy、Pillow 通常已包含在 ComfyUI 环境中；本包不需要模型下载。
如缺少依赖，用 **ComfyUI 自己的 Python 环境**安装 `requirements.txt`，避免替换已工作的 CUDA/PyTorch 版本。

更新：

```shell
git -C ComfyUI-JonGates pull --ff-only
```

## Cut (Qwen-Image 2.1) — JonGates

节点 ID：`JonGatesCutQwenImage21`，分类：`JonGates/Qwen`。

- `resolution`：1024–4096，每 32 一档，默认 2048。
- `tol_ratio`：目标面积允许偏差的调节参数，默认 1.0。
- `mode`：`crop` 等比缩放后中心裁切；`pad` 等比缩放后居中补边。
- `pad_color`：补边灰度，0 为黑，1 为白。
- 输出：`image`、`width`、`height`、`resolution`，宽高对齐到 32。

**resolution 不是最长边，而是目标面积的平方根。**
例如 4672×7008 的照片，在 `tol_ratio=0.8` 时：

| resolution | 实际处理尺寸 |
|---|---|
| 2048 | 1664×2496 |
| 3072 | 2496×3776 |
| 4096 | 3360×5024 |

尺寸选择沿用上游的面积、比例和对齐逻辑。节点会实际重采样图片；不能承诺逐像素不变或零裁切。
将 `resolution` 输出连接到 Qwen 2.1 文本编码节点的同名输入，并让 VAE 编码使用同一张处理图，可以保持两路尺寸一致。
这只解决尺寸一致性，不保证模型编辑时人物或细节零偏移。
4096 档约有 2048 档四倍像素；能否运行取决于显存、模型和采样配置。本项目的节点测试不代表完整模型能在 4096 档运行。

## Rotate Image (JonGates)

节点 ID：`JonGatesRotateImage`，分类：`JonGates/experimental`。

`angle` 为顺时针角度。首次旋转连接 `image`，输出图片与 `rotate_info`；继续旋转时，将二者都接入下一次旋转节点，角度会累加，并按原始尺寸计算输出边界。

- 保留上游的黑色补边、RGB 输出、双三次旋转逻辑。
- 当前只支持单张图片，多图批次会报错，不会静默丢弃后续图片。
- 任意角度旋转会插值，反向旋转不保证恢复原始像素。
- RGBA 输入会按黑底合成 RGB，不保留透明通道。
- 使用独立的 `JONGATES_ROTATE_INFO` 类型；迁移旋转链时，请同时替换整条链，不能直接混接 BlueBox 的旋转信息插口。

## 从 BlueBox 迁移

新增 JonGates 节点后，按同名插口重新连接并复制参数，保存为新工作流。
本包不注册 `CutQwenImage21` 或 `BlueBoxRotateImage` 的别名，不会覆盖上游节点。
Bridge 也已独立迁移，使用 `JonGatesBridge`；BlueBox 的其他节点不受影响。

## 参考风格控制 (JonGates)

节点 ID：`JonGatesReferenceStylePrompt`。这是保留给旧工作流的文字控制节点。编码器的 `image_1` 接待编辑原图、`image_2` 接风格参考图；直接双图编辑可能复制参考人物，泛化指令也可能几乎不改图。新建姿态参考流程建议使用下方的结构化分析、编辑计划与外部姿态控制链。

三个独立开关默认关闭：`change_scene`（场景可变）、`change_clothing`（服饰可变）、`change_pose`（姿势可变）。全部关闭时只要求迁移色彩、影调与光线氛围；开启时明确要求替换场景、衣服或调整姿势。人物身份、发型、发饰、独立配饰和随身物品始终要求保留。

第二输出 `consistency_strength` 连接“一致性无偏移”LoRA 的 `strength_model`：任一开关开启输出 `0.0`，全部关闭输出 `1.0`。这是为结构编辑避开一致性 LoRA 的限制，不适用于任意 LoRA。未接线时不会自动修改模型。第一输出仍兼容原工作流。

`style_description` 可以连接参考图分析文本，也可以不接，由 Qwen 直接观察第二张图。`extra_instruction` 填写补充意图。

这些开关生成文字约束及建议的 LoRA 强度，**不是遮罩或逐像素保护**。模型和 PE 均可能偏离指令；改变姿势或服饰时尤其需要检查身份、配饰和细节。该节点本身不读取图片，也不会修改分辨率。

## 参考编辑计划与姿态强度 (JonGates)

节点 ID：`JonGatesReferenceAnalysis` 与 `JonGatesReferenceEditPlan`。前者使用已有 PE GGUF 和 mmproj 做双图结构化观察，输出原人物、原服饰、原物品、原场景、原姿势以及参考场景、参考服饰、参考姿态、参考影调九个 JSON 字段。后者按三个开关选择字段，关闭的参考服装/场景/姿势描述不会进入生成提示词。旧 `JonGatesReferenceStylePrompt` 保持兼容。

建议连接：原图与参考图 → 双图结构化分析 → `reference_description`；编辑计划的 `prompt` → Qwen 编辑编码器。Qwen 的图片输入只接原人物照片。分析使用本机 `LLM` 目录的 PE-T2I GGUF 与 PE-I2I mmproj，需要已有支持 `Qwen35ChatHandler` 的 `llama-cpp-python`。本包不自动安装或升级 CUDA/llama 依赖。分析前释放 ComfyUI 已加载模型，分析结束关闭 LLM。

- 场景、服装和姿势三个开关分别决定替换或保留的文字要求。
- `pose_strength` 输出接 `ZImageFunControlnet` 的 `strength`。姿势开关关闭输出 0，开启输出设定强度（默认 1）。单独接文字输出不会产生空间姿态约束。
- 参考图 → `DWPreprocessor`（关闭脸部关键点）→ 等比补边对齐原图处理尺寸 → ControlNet 的 `image`。
- Qwen 2.1 Union 权重使用 `ModelPatchLoader` 加载；不使用普通 `ControlNetLoader`。需要另行安装 `comfyui_controlnet_aux` 并准备 DWPose 权重，这些不是本节点包的 Python 依赖。
- 姿态图必须先预览。多人、遮挡、出画肢体可能导致骨架提取错误。关闭脸部关键点也不等于锁定身份。

新模块首次安装后需要重启 ComfyUI 后端并刷新网页。开关组合、关闭字段隔离和强度输出有单元测试；生成效果仍受模型、参考骨架及描述准确度限制，不能保证换姿势后服装、身份和手持物逐项完全不变。分析器也可能误认物品，应查看 JSON 和最终提示词再判断问题。

## Bridge (JonGates)

节点 ID：`JonGatesBridge`，分类：`JonGates`。将上游图片接到 `image`，可选对比图片接到 `reference`。

- `block=never`：直接输出图像与遮罩。
- `block=if_not_continued`：生成预览并阻断下游；在节点右键菜单选择“在 JONGATES 编辑器中打开”，编辑并保存，再点击节点的“继续”按钮放行。
- 点击普通“运行”重新取上游图片；“继续”使用本次编辑后上传的图像和遮罩，只放行一次。
- `reference` 仅供编辑器比较，不改变主输出，也不决定是否阻断。
- 编辑器、HTTP 接口 `/jongates/bridge_*`、IndexedDB `JonGatesMaskEditorDB` 和临时目录 `JonGatesBridge` 独立于 BlueBox，可同时安装。
- 当前只支持单图；预览与编辑回填沿用 8-bit RGB 图片格式，不是浮点像素无损透传。批次输入会明确报错。
- 浏览器可能需要允许本站弹窗。重启后浏览器编辑记录仍可能存在，但服务器临时状态需要先运行节点重新建立。

Bridge 的 UI 按钮与独立编辑器由本包提供，无需保留 BlueBox 的前端脚本。入口只扩展 `JonGatesBridge`，不修改其他插件的菜单或全局种子行为。

`examples/jongates_image_tools.json` 是不含用户照片、模型路径的基础示例。导入后在 Load Image 中选择自己的图片。

## 目录结构

```text
ComfyUI-JonGates/
├── __init__.py             # 自动发现 nodes 下的节点模块
├── nodes/
│   ├── cut_qwen_image_21.py
│   ├── rotate_image.py
│   ├── bridge.py
│   ├── reference_style.py
│   ├── reference_analysis.py
│   └── reference_edit_plan.py
├── resources/             # Bridge 状态与 HTTP 接口
├── web/                   # Bridge 入口和独立编辑器
├── examples/
├── tests/
├── extension.json
├── pyproject.toml
├── requirements.txt
├── LICENSE
└── THIRD_PARTY_NOTICES.md
```

采用与 Goohaitools 类似的根入口、`nodes/`、`resources/`、`web/` 组织方式。新增节点模块时提供 `NODE_CLASS_MAPPINGS` 与 `NODE_DISPLAY_NAME_MAPPINGS`，并使用 `JonGates` 前缀避免冲突。

## 测试

```shell
python -m unittest discover -s tests -v
node tests/test_bridge_frontend.mjs
```

测试包括独立注册、97 个分辨率档位及多种比例的尺寸对齐、真实张量裁切/补边、旋转往返、Bridge 阻断/继续/遮罩/参考图、HTTP 接口和前端事件。无需加载生成模型。前端脚本测试不等于完整编辑器的人工视觉验收。

## 许可与来源

MIT。Cut、Rotate 和 Bridge/编辑器改编自 [ComfyUI-BlueBox](https://github.com/zhoutingxi/ComfyUI-BlueBox)，保留上游版权声明。
JonGates 的修改与包结构也以 MIT 发布。具体来源与版本见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
