"""Independent JonGates Bridge HTTP API, registered once during ComfyUI startup."""

import os
from pathlib import Path

from aiohttp import web

from . import bridge_state as core


def _input_file(filename):
    import folder_paths

    if not isinstance(filename, str) or not filename:
        return None
    root = Path(folder_paths.get_input_directory()).resolve()
    candidate = (root / filename).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    return str(candidate)


def _input_preview(filename):
    path = _input_file(filename)
    if not path:
        return None
    import folder_paths

    relative = Path(path).relative_to(Path(folder_paths.get_input_directory()).resolve())
    return {"filename": relative.name, "subfolder": relative.parent.as_posix() if len(relative.parts) > 1 else "", "type": "input"}


def register_routes(routes):
    @routes.post("/jongates/bridge_register")
    async def register(request):
        data = await request.json()
        node_id = str(data.get("node_id") or "")
        path = _input_file(data.get("image_filename"))
        if not node_id or not path:
            return web.json_response({"ok": False, "error": "A node ID and existing input image are required"}, status=400)
        mask_path = _input_file(data.get("mask_filename"))
        if data.get("mask_filename") and not mask_path:
            return web.json_response({"ok": False, "error": "Mask file not found"}, status=400)
        preview = _input_preview(data.get("preview_filename")) or _input_preview(data["image_filename"])
        core.set_bridge_image(node_id, path, mask_path, preview)
        return web.json_response({"ok": True})

    @routes.post("/jongates/bridge_continue")
    async def continue_bridge(request):
        data = await request.json()
        node_id = str(data.get("node_id") or "")
        path, _, _ = core.get_bridge_paths(node_id)
        if not node_id or not path or not os.path.isfile(path):
            return web.json_response({"ok": False, "error": "Run the Bridge once before continuing"}, status=400)
        core.set_bridge_continued(node_id, True)
        return web.json_response({"ok": True})

    @routes.get("/jongates/bridge_current_image")
    async def current_image(request):
        node_id = str(request.query.get("node_id") or "")
        path, _, preview = core.get_bridge_paths(node_id)
        if not node_id or not path or not os.path.isfile(path):
            return web.json_response({"ok": False, "error": "No image"})
        if not preview:
            preview = {"filename": os.path.basename(path), "subfolder": "", "type": "input"}
        return web.json_response({"ok": True, "image": preview})

    @routes.get("/jongates/bridge_reference_image")
    async def reference_image(request):
        path = core.get_bridge_reference(str(request.query.get("node_id") or ""))
        if not path or not os.path.isfile(path):
            return web.json_response({"ok": False, "error": "No reference"})
        return web.json_response({"ok": True, "image": {"filename": os.path.basename(path), "subfolder": "JonGatesBridge", "type": "temp"}})
