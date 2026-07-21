#!/usr/bin/env python3
from __future__ import annotations

import json
import re
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
def static_server():
    handler = lambda *args, **kwargs: SimpleHTTPRequestHandler(*args, directory=str(ROOT), **kwargs)
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
    config = (WEB / "config.js").read_text(encoding="utf-8")
    translations = load_json(WEB / "assets/translations.json")
    services = load_json(ROOT / "schemas/services.json")
    demos = load_json(WEB / "assets/demonstrations.json")

    if set(translations) != {"en", "es"}:
        fail("translations must contain exactly en and es")
    if set(translations["en"]) != set(translations["es"]):
        missing_en = sorted(set(translations["es"]) - set(translations["en"]))
        missing_es = sorted(set(translations["en"]) - set(translations["es"]))
        fail(f"translation parity mismatch; missing en={missing_en}, missing es={missing_es}")

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
    if (WEB / "assets/services.json").exists():
        fail("duplicate website service catalogue must not exist")
    if "demoMode: true" not in config or 'intakeEndpoint: ""' not in config:
        fail("website must remain in demonstration mode with a blank endpoint")
    if "noindex,nofollow" not in html:
        fail("validation alpha must remain noindex")

    active_codes = {item["code"] for item in services if item.get("status") == "active"}
    if active_codes != {"IVA", "CRM", "IOP"}:
        fail(f"unexpected active service set: {sorted(active_codes)}")
    for service in services:
        for lang in ("en", "es"):
            for field in ("name", "description", "ideal_for", "deliverables"):
                if not service.get(field, {}).get(lang):
                    fail(f"{service['code']} missing {field}.{lang}")
        if service.get("revision_limit") != 1:
            fail(f"{service['code']} must have one bounded revision")

    demo_service_codes = {item["service_code"] for item in demos}
    if demo_service_codes != active_codes:
        fail("demonstration coverage must match active services")
    forbidden_claims = ("testimonial", "client result", "guaranteed revenue")
    demo_text = json.dumps(demos, ensure_ascii=False).lower()
    if any(term in demo_text for term in forbidden_claims):
        fail("demonstrations contain prohibited claims")

    with static_server() as base:
        checks = {
            "/apps/web/": "International Growth Venture",
            "/apps/web/assets/app.js": "assertDataContracts",
            "/apps/web/assets/translations.json": '"en"',
            "/apps/web/assets/demonstrations.json": '"DEMO-IVA"',
            "/schemas/services.json": '"IVA"',
        }
        for path, marker in checks.items():
            with urlopen(base + path, timeout=5) as response:
                body = response.read().decode("utf-8")
                if response.status != 200 or marker not in body:
                    fail(f"static smoke check failed for {path}")

    print("website validation passed")


if __name__ == "__main__":
    main()
