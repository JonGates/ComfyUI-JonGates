import importlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from PIL import Image

from test_cut import load_package


class BridgeRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        package = load_package()
        routes_module = importlib.import_module(package.__name__ + ".resources.bridge_routes")
        self.core = routes_module.core
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.input = root / "input"
        self.input.mkdir()
        Image.new("RGB", (8, 8), "red").save(self.input / "image.png")
        Image.new("L", (8, 8), 128).save(self.input / "mask.png")
        Image.new("RGB", (8, 8), "blue").save(root / "outside.png")
        self.paths_patch = patch.dict(sys.modules, {"folder_paths": types.SimpleNamespace(get_input_directory=lambda: str(self.input))})
        self.paths_patch.start()
        self.core.clear_bridge("http-test")
        routes = web.RouteTableDef()
        routes_module.register_routes(routes)
        app = web.Application()
        app.add_routes(routes)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        self.paths_patch.stop()
        self.tmp.cleanup()

    async def test_register_current_continue_roundtrip(self):
        response = await self.client.post("/jongates/bridge_register", json={"node_id": "http-test", "image_filename": "image.png", "mask_filename": "mask.png"})
        self.assertEqual(response.status, 200)
        response = await self.client.get("/jongates/bridge_current_image?node_id=http-test")
        self.assertEqual((await response.json())["image"], {"filename": "image.png", "subfolder": "", "type": "input"})
        response = await self.client.post("/jongates/bridge_continue", json={"node_id": "http-test"})
        self.assertTrue((await response.json())["ok"])
        self.assertTrue(self.core.consume_bridge_continued("http-test"))
        self.assertFalse(self.core.consume_bridge_continued("http-test"))
        self.assertEqual((await self.client.get("/bluebox/bridge_current_image")).status, 404)

    async def test_reject_outside_input_and_uninitialized_continue(self):
        response = await self.client.post("/jongates/bridge_register", json={"node_id": "http-test", "image_filename": "../outside.png"})
        self.assertEqual(response.status, 400)
        response = await self.client.post("/jongates/bridge_continue", json={"node_id": "http-test"})
        self.assertEqual(response.status, 400)

    async def test_reference_endpoint(self):
        response = await self.client.get("/jongates/bridge_reference_image?node_id=http-test")
        self.assertFalse((await response.json())["ok"])
        self.core.set_bridge_reference("http-test", str(self.input / "image.png"))
        response = await self.client.get("/jongates/bridge_reference_image?node_id=http-test")
        self.assertEqual((await response.json())["image"]["subfolder"], "JonGatesBridge")


if __name__ == "__main__":
    unittest.main()
