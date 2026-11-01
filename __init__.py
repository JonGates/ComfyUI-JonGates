"""JonGates custom nodes: one discoverable Python module per node family."""

import importlib.util
import logging
from pathlib import Path
import sys

WEB_DIRECTORY = "./web"
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
_logger = logging.getLogger(__name__)

for _path in sorted((Path(__file__).parent / "nodes").glob("*.py")):
    if _path.name.startswith("_"):
        continue
    _name = f"{__name__}.nodes.{_path.stem}"
    _spec = importlib.util.spec_from_file_location(_name, _path)
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_name] = _module
    try:
        _spec.loader.exec_module(_module)
        _classes = getattr(_module, "NODE_CLASS_MAPPINGS", {})
        if NODE_CLASS_MAPPINGS.keys() & _classes.keys():
            raise ValueError(f"Duplicate node IDs in {_path.name}")
        NODE_CLASS_MAPPINGS.update(_classes)
        NODE_DISPLAY_NAME_MAPPINGS.update(
            getattr(_module, "NODE_DISPLAY_NAME_MAPPINGS", {})
        )
    except Exception:
        sys.modules.pop(_name, None)
        _logger.exception("[JonGates] Could not load %s", _path.name)

_logger.info("[JonGates] Loaded %d nodes", len(NODE_CLASS_MAPPINGS))

# ComfyUI imports extensions after creating PromptServer. Pure node unit tests
# can import this package without loading the ComfyUI server or starting CUDA.
_server_module = sys.modules.get("server")
_server = getattr(getattr(_server_module, "PromptServer", None), "instance", None)
if _server is not None and not getattr(_server, "_jongates_bridge_routes_registered", False):
    from .resources.bridge_routes import register_routes

    register_routes(_server.routes)
    _server._jongates_bridge_routes_registered = True

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
