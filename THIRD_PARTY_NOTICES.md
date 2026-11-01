# Third-party notices

`nodes/cut_qwen_image_21.py` and `nodes/rotate_image.py` are adapted from
[ComfyUI-BlueBox](https://github.com/zhoutingxi/ComfyUI-BlueBox), commit
`e46a4b32d6360d8234f400357e21925a36f05fc5`.

Bridge additions are adapted from the same revision's `bluebox_nodes.py`
(Bridge class only), `bluebox_core.py`, `web/bluebox.js` (Bridge editor entry),
and `web/mask-editor.html`. HTTP endpoints implement the same Bridge protocol
under an independent namespace. The editor retains its inline Lucide icon
attribution. All new branding, cache keys, node IDs and endpoints use JonGates.

Local changes: independent JonGates registration and category, Cut resolution
range 1024–4096, input validation, and explicit single-image rotation validation.
The MIT notice below applies to these upstream-derived portions.

MIT License

Copyright (c) 2026 zhoutingxi

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
