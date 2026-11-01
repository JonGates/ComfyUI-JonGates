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
BlueBox 的 Bridge 等其他节点仍由 BlueBox 提供。

`examples/jongates_image_tools.json` 是不含用户照片、模型路径的基础示例。导入后在 Load Image 中选择自己的图片。

## 目录结构

```text
ComfyUI-JonGates/
├── __init__.py             # 自动发现 nodes 下的节点模块
├── nodes/
│   ├── cut_qwen_image_21.py
│   └── rotate_image.py
├── resources/             # 预留共享资源
├── web/                   # 预留前端扩展
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
```

测试包括独立注册、97 个分辨率档位及多种比例的尺寸对齐、真实张量裁切/补边、旋转往返和无效输入校验。无需加载生成模型。

## 许可与来源

MIT。Cut 和 Rotate 算法改编自 [ComfyUI-BlueBox](https://github.com/zhoutingxi/ComfyUI-BlueBox)，保留上游版权声明。
JonGates 的修改与包结构也以 MIT 发布。具体来源与版本见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
