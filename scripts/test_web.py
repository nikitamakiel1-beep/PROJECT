#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps/web"


def fail(message: str) -> None:
    raise SystemExit(f"website validation failed: {message}")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@contextmanager
def static_server(directory: Path):
    handler = lambda *args, **kwargs: SimpleHTTPRequestHandler(*args, directory=str(directory), **kwargs)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def main() -> None:
    html = (WEB / "index.html").read_text(encoding="utf-8")
    app = (WEB / "assets/app.js").read_text(encoding="utf-8")
    config_text = (WEB / "config.js").read_text(encoding="utf-8")
    translations = load_json(WEB / "assets/translations.json")
    services = load_json(ROOT / "schemas/services.json")
    demos = load_json(WEB / "assets/demonstrations.json")
    readiness = load_json(ROOT / "config/pre-client-readiness.json")
    routes = load_json(ROOT / "config/web-route-content.json")["routes"]

    if set(translations) != {"en", "es"}:
        fail("translations must contain exactly en and es")
    if set(translations["en"]) != set(translations["es"]):
        fail("translation parity mismatch")

    referenced_keys = set(re.findall(r'data-i18n="([^"]+)"', html))
    referenced_keys.update(re.findall(r"(?<![A-Za-z0-9_])t\('([^']+)'\)", app))
    missing = sorted(referenced_keys - set(translations["en"]))
    if missing:
        fail(f"missing translation keys: {missing}")

    ids = re.findall(r'id="([^"]+)"', html)
    if len(ids) != len(set(ids)):
        fail("duplicate HTML id")
    for target in re.findall(r'href="#([^"]+)"', html):
        if target not in ids:
            fail(f"anchor target not found: {target}")

    if "../../schemas/services.json" not in app:
        fail("website must load the canonical service catalogue")
    if "demoMode: true" not in config_text or 'intakeEndpoint: ""' not in config_text:
        fail("website must remain in demonstration mode with a blank endpoint")
    if "noindex,nofollow" not in html:
        fail("source website must remain noindex")

    expected_routes = {route for route in readiness["required_website_routes"] if route != "index.html"}
    if set(routes) != expected_routes:
        fail("route content does not match readiness contract")
    if any(set(value) != {"en", "es"} for value in routes.values()):
        fail("generated route language parity mismatch")

    active_codes = {item["code"] for item in services if item.get("status") == "active"}
    if active_codes != {"IVA", "CRM", "IOP"}:
        fail(f"unexpected active service set: {sorted(active_codes)}")
    if {item["service_code"] for item in demos} != active_codes:
        fail("demonstration coverage must match active services")
    if any(service.get("revision_limit") != 1 for service in services):
        fail("all services must have one bounded revision")

    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir) / "preview"
        subprocess.run([
            sys.executable, str(ROOT / "scripts/build_web_release.py"),
            "--profile", "preview", "--output", str(output),
        ], cwd=ROOT, check=True, capture_output=True, text=True)
        with static_server(output) as base:
            checks = {
                "/": "International Growth Venture",
                "/services.html": "Services",
                "/how-it-works.html": "How it works",
                "/examples.html": "Examples",
                "/about.html": "About",
                "/insights.html": "Insights",
                "/contact.html": "Assessment",
                "/privacy.html": "Privacy",
                "/cookies.html": "Cookies",
                "/legal.html": "Legal",
                "/assets/app.js": "assertDataContracts",
                "/assets/demonstrations.json": '"DEMO-IVA"',
                "/schemas/services.json": '"IVA"',
            }
            for path, marker in checks.items():
                with urlopen(base + path, timeout=5) as response:
                    body = response.read().decode("utf-8")
                    if response.status != 200 or marker not in body:
                        fail(f"static smoke check failed for {path}")
        info = load_json(output / "RELEASE_BUILD.json")
        if info["route_count"] != 10 or info["indexable"] is not False:
            fail("preview release metadata is invalid")

    print("website validation passed: generated ten-route bilingual preview")


if __name__ == "__main__":
    main()
