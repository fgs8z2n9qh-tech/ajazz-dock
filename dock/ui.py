"""Local Flask config UI + JSON API for the AKP03 controller."""
from __future__ import annotations

import io
import os
import sys
from typing import Optional

from flask import Flask, jsonify, request, send_file
from werkzeug.utils import secure_filename

from .config import Config, _migrate, config_dir
from .images import render_face

if getattr(sys, "frozen", False):
    # PyInstaller: web assets are added at dock/web under the bundle root.
    WEB_DIR = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
                           "dock", "web")
else:
    WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
HOST = "127.0.0.1"
PORT = 8773


def create_app(controller, on_show_window=None) -> Flask:
    app = Flask(__name__, static_folder=WEB_DIR, static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
    icon_dir = os.path.join(config_dir(), "icons")
    os.makedirs(icon_dir, exist_ok=True)

    @app.get("/")
    def index():
        return send_file(os.path.join(WEB_DIR, "index.html"))

    @app.post("/api/upload")
    def upload():
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify({"ok": False, "error": "no file"}), 400
        name = secure_filename(f.filename) or "icon.png"
        base, ext = os.path.splitext(name)
        if ext.lower() not in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".ico"):
            return jsonify({"ok": False, "error": "unsupported type"}), 400
        dest = os.path.join(icon_dir, name)
        i = 1
        while os.path.exists(dest):
            dest = os.path.join(icon_dir, f"{base}_{i}{ext}")
            i += 1
        f.save(dest)
        return jsonify({"ok": True, "path": dest})

    @app.get("/api/config")
    def get_config():
        return jsonify(controller.config.data)

    @app.post("/api/config")
    def post_config():
        data = request.get_json(force=True)
        controller.config = Config(_migrate(data))
        controller.config.save()
        controller.request_reload()
        return jsonify({"ok": True, "status": controller.status()})

    @app.get("/api/status")
    def status():
        return jsonify(controller.status())

    @app.post("/api/reload")
    def reload():
        controller.request_reload()
        return jsonify({"ok": True})

    @app.post("/api/render")
    def render():
        """Render a binding face to PNG for live preview (no save)."""
        item = request.get_json(force=True) or {}
        img = render_face(item).resize((120, 120))  # NEAREST default keeps device pixels
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png")

    @app.post("/api/test")
    def test():
        action = (request.get_json(force=True) or {}).get("action")
        controller.engine.execute(action)
        return jsonify({"ok": True})

    @app.post("/api/goto")
    def goto():
        body = request.get_json(force=True) or {}
        if "profile" in body and body["profile"]:
            controller.set_profile(body["profile"])
        if "page_index" in body:
            controller.goto_page(int(body["page_index"]))
        return jsonify({"ok": True, "status": controller.status()})

    @app.post("/api/brightness")
    def brightness():
        v = int((request.get_json(force=True) or {}).get("value", 70))
        controller.set_brightness(v)
        return jsonify({"ok": True})

    @app.post("/api/show_window")
    def show_window():
        if on_show_window:
            on_show_window()
        return jsonify({"ok": True})

    return app


def run_ui(controller, host: str = HOST, port: int = PORT, on_show_window=None) -> None:
    app = create_app(controller, on_show_window=on_show_window)
    # threaded so preview renders don't block API calls; no reloader in-thread.
    app.run(host=host, port=port, threaded=True, use_reloader=False)
