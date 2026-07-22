#!/usr/bin/env python3
"""Build a reproducible preview, staging or live website artifact."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import html
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
WEB_SOURCE = ROOT / "apps" / "web"
SERVICE_SOURCE = ROOT / "schemas" / "services.json"
READINESS_CONFIG = ROOT / "config" / "pre-client-readiness.json"
ROUTE_CONTENT = ROOT / "config" / "web-route-content.json"
SERVICE_FETCH_SOURCE = "fetchJson('../../schemas/services.json')"
SERVICE_FETCH_RELEASE = "fetchJson('schemas/services.json')"

LIVE_GATES = (
    "provider_a01_9_of_9",
    "provider_a02_idempotency",
    "provider_neural_bridge",
    "provider_cleanup_verified",
    "privacy_professional_approval",
    "legal_and_invoicing_professional_approval",
    "website_publication_qa",
    "human_live_release_approval",
)


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _evidence(path: Path | None) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path else {}


def _validate_profile(profile: str, endpoint: str, evidence: dict) -> None:
    if profile == "preview":
        if endpoint:
            raise SystemExit("preview build failed: endpoint must be blank")
        return
    if not endpoint.startswith("https://"):
        raise SystemExit(f"{profile} build failed: an HTTPS endpoint is required")
    if profile == "live":
        missing = [key for key in LIVE_GATES if evidence.get(key) is not True]
        if missing:
            raise SystemExit(f"live build failed: activation gates are incomplete: {', '.join(missing)}")


def _route_page(filename: str, content: dict, *, live: bool) -> str:
    en = content["en"]
    es = content["es"]
    robots = "index,follow" if live else "noindex,nofollow"
    nav = [
        ("index.html", "Home / Inicio"),
        ("services.html", "Services / Servicios"),
        ("how-it-works.html", "How it works / Cómo funciona"),
        ("examples.html", "Examples / Ejemplos"),
        ("about.html", "About / Nosotros"),
        ("insights.html", "Insights / Ideas"),
        ("contact.html", "Assessment / Evaluación"),
    ]
    nav_html = "".join(f'<a href="{href}">{html.escape(label)}</a>' for href, label in nav)
    en_items = "".join(f"<li>{html.escape(item)}</li>" for item in en["sections"])
    es_items = "".join(f"<li>{html.escape(item)}</li>" for item in es["sections"])
    return f"""<!doctype html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{html.escape(en['intro'])}">
  <meta name="robots" content="{robots}">
  <meta name="color-scheme" content="light dark">
  <title>{html.escape(en['title'])} — International Growth Venture</title>
  <script>
    (() => {{
      const saved = localStorage.getItem('igv-theme');
      const preferred = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      document.documentElement.dataset.theme = saved || preferred;
    }})();
  </script>
  <link rel="stylesheet" href="assets/styles.css">
  <style>
    .route-hero{{padding-block:clamp(5rem,10vw,9rem) 3rem;max-width:920px}}
    .route-hero h1{{font-size:clamp(2.7rem,7vw,5.8rem);line-height:.96;letter-spacing:-.05em;max-width:18ch}}
    .route-grid{{display:grid;grid-template-columns:1fr 1fr;gap:1rem;padding-bottom:6rem}}
    .route-card{{padding:clamp(1.3rem,3vw,2.2rem);border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);box-shadow:var(--shadow)}}
    .route-card li,.route-card p{{color:var(--muted)}}
    .route-controls{{display:flex;gap:.5rem;flex-wrap:wrap}}
    .route-hidden{{display:none}}
    footer nav{{display:flex;gap:1rem;flex-wrap:wrap}}
    @media(max-width:760px){{.route-grid{{grid-template-columns:1fr}}}}
  </style>
</head>
<body data-route="{html.escape(filename)}">
  <a class="skip" href="#main">Skip to content</a>
  <header class="site-header">
    <a class="brand" href="index.html"><span class="brand-mark" aria-hidden="true">IG</span><span>International Growth Venture</span></a>
    <nav aria-label="Primary navigation">{nav_html}</nav>
    <div class="route-controls">
      <button id="language" type="button">ES</button>
      <button id="theme" type="button" aria-label="Change theme">◐</button>
    </div>
  </header>
  <main id="main">
    <section class="route-hero shell">
      <div id="en">
        <p class="eyebrow">{html.escape(en['eyebrow'])}</p>
        <h1>{html.escape(en['title'])}</h1>
        <p class="lead">{html.escape(en['intro'])}</p>
      </div>
      <div id="es" class="route-hidden">
        <p class="eyebrow">{html.escape(es['eyebrow'])}</p>
        <h1>{html.escape(es['title'])}</h1>
        <p class="lead">{html.escape(es['intro'])}</p>
      </div>
      <div class="mode-banner" role="note"><strong>Pre-client gate</strong><span>Source and construction ready. Live intake still requires provider, legal, privacy and human release evidence.</span></div>
    </section>
    <section class="route-grid shell">
      <article class="route-card" id="en-list"><h2>Controlled scope</h2><ul>{en_items}</ul><a class="button primary" href="index.html#assessment">Open assessment</a></article>
      <article class="route-card route-hidden" id="es-list"><h2>Alcance controlado</h2><ul>{es_items}</ul><a class="button primary" href="index.html#assessment">Abrir evaluación</a></article>
      <article class="route-card"><h2>Safety boundary / Límite de seguridad</h2><p>No client claims, no automatic outreach, no autonomous price changes and no live data capture without approved gates.</p></article>
    </section>
  </main>
  <footer class="shell"><p>© <span id="year"></span> International Growth Venture</p><nav><a href="privacy.html">Privacy</a><a href="cookies.html">Cookies</a><a href="legal.html">Legal</a></nav></footer>
  <script>
    const language = document.getElementById('language');
    let locale = localStorage.getItem('igv-language') === 'es' ? 'es' : 'en';
    function renderLocale() {{
      const spanish = locale === 'es';
      document.getElementById('en').classList.toggle('route-hidden', spanish);
      document.getElementById('en-list').classList.toggle('route-hidden', spanish);
      document.getElementById('es').classList.toggle('route-hidden', !spanish);
      document.getElementById('es-list').classList.toggle('route-hidden', !spanish);
      language.textContent = spanish ? 'EN' : 'ES';
      document.documentElement.lang = locale;
    }}
    language.addEventListener('click', () => {{
      locale = locale === 'en' ? 'es' : 'en';
      localStorage.setItem('igv-language', locale);
      renderLocale();
    }});
    document.getElementById('theme').addEventListener('click', () => {{
      const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = next;
      localStorage.setItem('igv-theme', next);
    }});
    document.getElementById('year').textContent = new Date().getFullYear();
    renderLocale();
  </script>
</body>
</html>
"""


def build(output: Path, *, profile: str, endpoint: str, evidence: dict) -> dict:
    _validate_profile(profile, endpoint, evidence)
    readiness = json.loads(READINESS_CONFIG.read_text(encoding="utf-8"))
    routes = json.loads(ROUTE_CONTENT.read_text(encoding="utf-8"))["routes"]
    expected = {route for route in readiness["required_website_routes"] if route != "index.html"}
    if set(routes) != expected:
        raise SystemExit("release build failed: route content does not match the readiness contract")

    if output.exists():
        shutil.rmtree(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(WEB_SOURCE, output)

    schema_dir = output / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SERVICE_SOURCE, schema_dir / "services.json")

    app_path = output / "assets" / "app.js"
    app_text = app_path.read_text(encoding="utf-8")
    if SERVICE_FETCH_SOURCE not in app_text:
        raise SystemExit("release build failed: canonical service fetch expression changed")
    app_path.write_text(app_text.replace(SERVICE_FETCH_SOURCE, SERVICE_FETCH_RELEASE), encoding="utf-8")

    live = profile == "live"
    config = {
        "deploymentMode": profile,
        "demoMode": profile == "preview",
        "syntheticOnly": not live,
        "intakeEndpoint": endpoint,
        "consentVersion": "assessment-v1-2026-07",
        "requestTimeoutMs": 12000,
    }
    (output / "config.js").write_text(
        "window.VENTURE_CONFIG = " + json.dumps(config, indent=2) + ";\n",
        encoding="utf-8",
    )

    index_path = output / "index.html"
    index_html = index_path.read_text(encoding="utf-8")
    if "noindex,nofollow" not in index_html:
        raise SystemExit("release build failed: source index lost noindex")
    route_rewrites = {
        'href="#services"': 'href="services.html"',
        'href="#fit"': 'href="about.html"',
        'href="#process"': 'href="how-it-works.html"',
        'href="#examples"': 'href="examples.html"',
        'href="#assessment"': 'href="contact.html"',
    }
    for old, new in route_rewrites.items():
        index_html = index_html.replace(old, new)
    if live:
        index_html = index_html.replace("noindex,nofollow", "index,follow")
    index_path.write_text(index_html, encoding="utf-8")

    for filename, content in routes.items():
        (output / filename).write_text(_route_page(filename, content, live=live), encoding="utf-8")

    (output / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n" if live else "User-agent: *\nDisallow: /\n",
        encoding="utf-8",
    )
    (output / "_headers").write_text(
        "/*\n"
        "  X-Content-Type-Options: nosniff\n"
        "  Referrer-Policy: strict-origin-when-cross-origin\n"
        "  Permissions-Policy: camera=(), microphone=(), geolocation=()\n"
        "  Cross-Origin-Opener-Policy: same-origin\n"
        "  Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' https:; base-uri 'self'; form-action 'self' https:; frame-ancestors 'none'\n",
        encoding="utf-8",
    )

    evidence_digest = ""
    if evidence:
        canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
        evidence_digest = sha256(canonical.encode("utf-8")).hexdigest()

    build_info = {
        "artifact": "international-growth-venture-web-release",
        "profile": profile,
        "source_ready": True,
        "intake_enabled": bool(endpoint) and profile in {"staging", "live"},
        "synthetic_only": not live,
        "indexable": live,
        "route_count": len(readiness["required_website_routes"]),
        "routes": readiness["required_website_routes"],
        "canonical_service_source": "schemas/services.json",
        "activation_evidence_digest": evidence_digest,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "source_date_epoch": os.environ.get("SOURCE_DATE_EPOCH", ""),
    }
    (output / "RELEASE_BUILD.json").write_text(json.dumps(build_info, indent=2) + "\n", encoding="utf-8")

    files = sorted(path for path in output.rglob("*") if path.is_file() and path.name != "SHA256SUMS")
    (output / "SHA256SUMS").write_text(
        "\n".join(f"{file_sha256(path)}  {path.relative_to(output).as_posix()}" for path in files) + "\n",
        encoding="utf-8",
    )
    return build_info


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("preview", "staging", "live"), default="preview")
    parser.add_argument("--endpoint", default="")
    parser.add_argument("--activation-evidence", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "web-release")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    info = build(
        output.resolve(),
        profile=args.profile,
        endpoint=args.endpoint,
        evidence=_evidence(args.activation_evidence),
    )
    print(json.dumps({"ok": True, "output": str(output), **info}, indent=2))


if __name__ == "__main__":
    main()
