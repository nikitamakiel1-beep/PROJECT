#!/usr/bin/env python3
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path("/opt/conway-bootstrap")
INSTALL_ROOT = Path("/opt/conway-replicatio")
STATUS_FILE = ROOT / "status.json"
INSTALL_LOG = ROOT / "install.log"
SETUP_CODE = os.environ.get("SETUP_CODE", "")
WORKER_HOST = os.environ.get("WORKER_HOST", "")
WORKER_URL = os.environ.get("WORKER_URL", "")
REPO = "nikitamakiel1-beep/Conway-Replicatio"
BRANCH = "feature/conway-colonial-integration"
OWNER = "nikitamakiel1-beep"
LOCAL_MODEL = "qwen3:4b"
LOVABLE_ORIGIN = "https://conway-replicatio.lovable.app"
MAX_BODY = 32_768

state_lock = threading.Lock()
install_lock = threading.Lock()
rate_lock = threading.Lock()
rate = {}


def atomic_json(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def read_status():
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {
            "stage": "ready_for_owner",
            "progress": 0,
            "message": "Oracle host is ready. Enter the one-time code, GitHub read token and public Creator wallet.",
            "installed": False,
            "sealed": False,
            "startedAt": None,
            "completedAt": None,
        }


def update_status(**updates):
    with state_lock:
        status = read_status()
        status.update(updates)
        atomic_json(STATUS_FILE, status)
        return status


def constant_equal(a, b):
    return bool(a and b and hmac.compare_digest(str(a), str(b)))


def valid_code(code):
    status = read_status()
    return not status.get("sealed") and constant_equal(code, SETUP_CODE)


def public_wallet(value):
    return bool(re.fullmatch(r"0x[a-fA-F0-9]{40}", value or ""))


def client_ip(handler):
    forwarded = handler.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    return forwarded or handler.client_address[0]


def rate_allowed(ip):
    now = time.time()
    with rate_lock:
        bucket = [stamp for stamp in rate.get(ip, []) if now - stamp < 900]
        if len(bucket) >= 12:
            rate[ip] = bucket
            return False
        bucket.append(now)
        rate[ip] = bucket
        return True


def github_json(path, token):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "conway-replicatio-browser-bootstrap",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def verify_github_token(token):
    if len(token) < 20 or len(token) > 1024:
        raise ValueError("GitHub token format is invalid")
    user = github_json("/user", token)
    if user.get("login") != OWNER:
        raise ValueError("The GitHub token does not belong to the required owner account")
    repo = github_json("/repos/" + REPO, token)
    if repo.get("full_name") != REPO:
        raise ValueError("The token cannot read the Conway-Replicatio repository")


def run(args, *, cwd=None, env=None, timeout=None):
    with INSTALL_LOG.open("a", encoding="utf-8") as log:
        log.write("\n$ " + " ".join(args[:3]) + (" ..." if len(args) > 3 else "") + "\n")
        log.flush()
        proc = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {proc.returncode}: {args[0]} {args[1] if len(args) > 1 else ''}")


def api(path, control_token, method="GET", payload=None, timeout=30):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": "Bearer " + control_token,
        "Content-Type": "application/json",
    }
    if method != "GET":
        headers["Idempotency-Key"] = "browser-bootstrap-" + secrets.token_hex(12)
    req = urllib.request.Request(
        "http://127.0.0.1:8080" + path,
        data=body,
        method=method,
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def wait_for_worker(control_token, seconds=600):
    deadline = time.time() + seconds
    last = None
    while time.time() < deadline:
        try:
            req = urllib.request.Request("http://127.0.0.1:8080/health")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    return data
        except Exception as exc:
            last = exc
        time.sleep(5)
    raise RuntimeError("Worker did not become healthy in time" + (f": {last}" if last else ""))


def read_control_token():
    env_file = INSTALL_ROOT / ".env"
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("REPLICATIO_CONTROL_TOKEN="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def write_compose():
    compose = '''services:
  ollama:
    image: ollama/ollama:latest
    restart: unless-stopped
    network_mode: host
    environment:
      OLLAMA_HOST: "127.0.0.1:11434"
      OLLAMA_KEEP_ALIVE: "10m"
      OLLAMA_NUM_PARALLEL: "1"
      OLLAMA_MAX_LOADED_MODELS: "1"
    volumes:
      - ./ollama:/root/.ollama
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"

  worker:
    build:
      context: ./app
    restart: unless-stopped
    network_mode: host
    env_file:
      - .env
    environment:
      PORT: "8080"
      REPLICATIO_INTERNAL_PORT: "8081"
      REPLICATIO_DATA_HOME: "/data"
      AUTOMATON_HOME: "/data/.automaton"
      REPLICATIO_AUTOSTART: "true"
      REPLICATIO_REQUIRE_FIRST_CHECKPOINT: "true"
      OLLAMA_BASE_URL: "http://127.0.0.1:11434"
      REPLICATIO_LOCAL_MODEL: "qwen3:4b"
    volumes:
      - ./data:/data
    depends_on:
      - ollama
    logging:
      driver: json-file
      options:
        max-size: "20m"
        max-file: "5"
'''
    (INSTALL_ROOT / "compose.yml").write_text(compose, encoding="utf-8")
    os.chmod(INSTALL_ROOT / "compose.yml", 0o600)


def install_worker(github_token, creator_address, agent_name):
    with install_lock:
        try:
            update_status(stage="verifying_owner", progress=5, message="Verifying GitHub owner and repository access", startedAt=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            verify_github_token(github_token)

            if (INSTALL_ROOT / "app").exists():
                shutil.rmtree(INSTALL_ROOT / "app")
            INSTALL_ROOT.mkdir(parents=True, exist_ok=True)
            for directory in ("data", "ollama"):
                path = INSTALL_ROOT / directory
                path.mkdir(parents=True, exist_ok=True)
                os.chmod(path, 0o700)

            update_status(stage="cloning", progress=12, message="Cloning the private Conway-Replicatio worker without storing the GitHub token")
            askpass = ROOT / ("askpass-" + secrets.token_hex(8) + ".sh")
            askpass.write_text('#!/bin/sh\ncase "$1" in\n  *Username*) echo "x-access-token" ;;\n  *Password*) printf "%s\\n" "$GITHUB_TOKEN" ;;\nesac\n', encoding="utf-8")
            os.chmod(askpass, 0o700)
            clone_env = os.environ.copy()
            clone_env.update({
                "GITHUB_TOKEN": github_token,
                "GIT_ASKPASS": str(askpass),
                "GIT_TERMINAL_PROMPT": "0",
            })
            try:
                run([
                    "git", "clone", "--branch", BRANCH, "--single-branch",
                    "https://github.com/" + REPO + ".git", str(INSTALL_ROOT / "app")
                ], env=clone_env, timeout=300)
            finally:
                github_token = ""
                clone_env.pop("GITHUB_TOKEN", None)
                try:
                    askpass.unlink()
                except FileNotFoundError:
                    pass

            control_token = secrets.token_hex(32)
            honey_token = secrets.token_hex(32)
            env_text = "\n".join([
                "REPLICATIO_CONTROL_TOKEN=" + control_token,
                "REPLICATIO_HONEY_OPERATOR_TOKEN=" + honey_token,
                "REPLICATIO_ALLOWED_ORIGIN=" + LOVABLE_ORIGIN,
                "REPLICATIO_LOCAL_MODEL=" + LOCAL_MODEL,
                "OLLAMA_BASE_URL=http://127.0.0.1:11434",
                "",
            ])
            (INSTALL_ROOT / ".env").write_text(env_text, encoding="utf-8")
            os.chmod(INSTALL_ROOT / ".env", 0o600)
            write_compose()

            update_status(stage="building", progress=25, message="Building the pinned Conway Automaton + Replicatio runtime on Oracle ARM")
            run(["docker", "compose", "-f", "compose.yml", "build", "worker"], cwd=INSTALL_ROOT, timeout=3600)

            update_status(stage="local_model", progress=55, message="Starting Ollama and downloading the free qwen3:4b model")
            run(["docker", "compose", "-f", "compose.yml", "up", "-d", "ollama"], cwd=INSTALL_ROOT, timeout=180)
            run(["docker", "compose", "-f", "compose.yml", "exec", "-T", "ollama", "ollama", "pull", LOCAL_MODEL], cwd=INSTALL_ROOT, timeout=3600)

            update_status(stage="worker", progress=68, message="Starting the protected Replicatio worker")
            run(["docker", "compose", "-f", "compose.yml", "up", "-d", "worker"], cwd=INSTALL_ROOT, timeout=300)
            wait_for_worker(control_token)

            update_status(stage="bootstrap", progress=76, message="Generating the Agent Wallet and zero-spend local-only configuration")
            bootstrap = {
                "name": agent_name,
                "genesisPrompt": "Operate continuously in a cautious, diagnostic-first mode using only zero-cost local inference. Create genuine useful work and maintain accurate records, but do not spend money, transfer assets, purchase services, create children, contact external parties, send unsolicited messages, or enable payouts unless the owner explicitly changes the corresponding policy. Prefer reversible local work and surface proposed external actions for owner review.",
                "creatorAddress": creator_address,
                "conwayApiKey": "local_ollama_only",
                "autoProvision": False,
                "inferenceModel": LOCAL_MODEL,
                "ollamaBaseUrl": "http://127.0.0.1:11434",
                "limits": {
                    "maxChildren": 0,
                    "maxChildBudgetCents": 0,
                    "minimumReserveCents": 500,
                },
                "treasuryPolicy": {
                    "maxSingleTransferCents": 0,
                    "maxHourlyTransferCents": 0,
                    "maxDailyTransferCents": 0,
                    "minimumReserveCents": 500,
                    "maxX402PaymentCents": 0,
                    "maxInferenceDailyCents": 0,
                    "requireConfirmationAboveCents": 0,
                    "x402AllowedDomains": [],
                },
                "honeyPolicy": {"enabled": False},
            }
            api("/api/v1/bootstrap", control_token, method="POST", payload=bootstrap, timeout=180)

            update_status(stage="local_routing", progress=84, message="Locking inference routing to free local Ollama and disabling paid baseline models")
            run(["docker", "compose", "-f", "compose.yml", "exec", "-T", "worker", "node", "scripts/configure-local-inference.mjs", LOCAL_MODEL], cwd=INSTALL_ROOT, timeout=120)

            update_status(stage="checkpoint", progress=90, message="Creating the mandatory pre-activation integrity checkpoint")
            api("/api/v1/backups/checkpoint", control_token, method="POST", payload={"confirmation": "CREATE CHECKPOINT"}, timeout=120)
            ready = api("/api/v1/readiness", control_token, timeout=60)
            if not ready.get("data", {}).get("readyForActivation"):
                raise RuntimeError("Worker readiness gate did not pass after checkpoint")

            update_status(stage="starting", progress=95, message="Starting Replicatio under the crash-recovery watchdog")
            api("/api/v1/start", control_token, method="POST", payload={}, timeout=60)

            update_status(
                stage="complete",
                progress=100,
                message="Replicatio is running with local qwen3:4b inference, zero spending, zero children and Honey payouts disabled.",
                installed=True,
                completedAt=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                workerUrl=WORKER_URL,
                tokenAcknowledged=False,
            )
        except Exception as exc:
            update_status(stage="error", message=str(exc), installed=False)


def page_html():
    status = read_status()
    sealed = bool(status.get("sealed"))
    stage = html.escape(str(status.get("stage", "ready_for_owner")))
    message = html.escape(str(status.get("message", "")))
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conway Replicatio · Oracle Setup</title>
<style>
:root{{color-scheme:dark}}body{{margin:0;background:#07100f;color:#edf7f2;font:15px/1.55 system-ui,sans-serif}}main{{max-width:820px;margin:0 auto;padding:42px 20px}}.card{{border:1px solid #ffffff1c;background:#ffffff08;border-radius:24px;padding:24px;margin:16px 0}}h1{{font-size:30px;margin:0 0 8px}}h2{{font-size:18px}}label{{display:block;margin:14px 0 6px;color:#b8c9c1}}input{{box-sizing:border-box;width:100%;padding:12px;border-radius:12px;border:1px solid #ffffff24;background:#07100f;color:white}}button{{margin-top:18px;padding:12px 18px;border:0;border-radius:12px;background:#6ee7b7;color:#04100c;font-weight:700;cursor:pointer}}code{{word-break:break-all;color:#9ff2ce}}.muted{{color:#91a39b}}.ok{{color:#7ee4b8}}.bad{{color:#fda4af}}progress{{width:100%;height:10px}}#secret{{display:none;border:1px solid #6ee7b755;background:#6ee7b70d}}pre{{white-space:pre-wrap;word-break:break-word}}</style></head>
<body><main><p class="muted">Conway Replicatio · browser-only Oracle worker</p><h1>Free cloud worker setup</h1>
<p class="muted">No local terminal, SSH, Docker or Conway website login is required. The GitHub token is used in memory for one private clone and is then discarded.</p>
<div class="card"><strong>Current stage:</strong> <span id="stage">{stage}</span><p id="msg">{message}</p><progress id="progress" max="100" value="{int(status.get('progress',0) or 0)}"></progress></div>
{('<div class="card"><h2>Setup sealed</h2><p>The one-time setup portal has been sealed. The worker remains available through the Lovable control plane.</p></div>' if sealed else '''<div class="card"><h2>Owner setup</h2>
<label>One-time Oracle setup code</label><input id="code" type="password" autocomplete="off" placeholder="Shown in Resource Manager outputs">
<label>GitHub fine-grained read token</label><input id="token" type="password" autocomplete="off" placeholder="github_pat_…">
<p class="muted">Owner must be nikitamakiel1-beep; repository access only to Conway-Replicatio; Contents read-only.</p>
<label>Public Creator Share wallet</label><input id="wallet" autocomplete="off" placeholder="0x…">
<label>Agent name</label><input id="agent" value="Replicatio-Prime" maxlength="80">
<button id="install">Install and start free worker</button><p id="formMsg" class="muted"></p></div>
<div class="card" id="secret"><h2>Save this once</h2><p>Worker URL:</p><code id="workerUrl"></code><p>Control token:</p><code id="controlToken"></code><p class="muted">Copy both into Lovable → /setup → Connect an existing worker. The token will disappear after you confirm it is saved.</p><button id="ack">I saved the control token — seal setup</button></div>''')}
<div class="card"><h2>First-boot safety</h2><p class="muted">Local qwen3:4b inference · spending disabled · children disabled · Honey payouts disabled · HTTPS only · no public SSH · wallet private key stays inside Oracle persistent storage.</p></div>
<script>
const $=id=>document.getElementById(id);let polling=null;
async function post(path,obj){{const r=await fetch(path,{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify(obj)}});const j=await r.json();if(!r.ok)throw new Error(j.error||'Request failed');return j}}
async function refresh(){{const code=$('code')?.value||'';if(!code)return;try{{const j=await post('/setup/status',{{code}});$('stage').textContent=j.stage;$('msg').textContent=j.message||'';$('progress').value=j.progress||0;if(j.installed&&j.controlToken){{$('secret').style.display='block';$('workerUrl').textContent=j.workerUrl;$('controlToken').textContent=j.controlToken;clearInterval(polling)}}}}catch(e){{}}}}
$('install')?.addEventListener('click',async()=>{{$('formMsg').textContent='';try{{const j=await post('/setup/install',{{code:$('code').value,githubToken:$('token').value,creatorAddress:$('wallet').value,agentName:$('agent').value}});$('token').value='';$('formMsg').textContent=j.message;polling=setInterval(refresh,5000);refresh()}}catch(e){{$('formMsg').textContent=e.message;$('formMsg').className='bad'}}}});
$('ack')?.addEventListener('click',async()=>{{try{{await post('/setup/ack',{{code:$('code').value}});$('controlToken').textContent='SEALED';$('secret').innerHTML='<h2 class="ok">Setup sealed</h2><p>The control token will no longer be revealed by this portal.</p>'}}catch(e){{alert(e.message)}}}});
</script></main></body></html>'''


class Handler(BaseHTTPRequestHandler):
    server_version = "ReplicatioSetup/1.0"

    def log_message(self, fmt, *args):
        print("[portal]", self.command, self.path.split("?", 1)[0], client_ip(self), flush=True)

    def security_headers(self, code=200, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()

    def json_response(self, code, payload):
        raw = json.dumps(payload).encode("utf-8")
        self.security_headers(code)
        self.wfile.write(raw)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0 or length > MAX_BODY:
            raise ValueError("Invalid request size")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        if self.path.rstrip("/") == "/setup":
            raw = page_html().encode("utf-8")
            self.security_headers(200, "text/html; charset=utf-8")
            self.wfile.write(raw)
            return
        self.json_response(404, {"error": "not found"})

    def do_POST(self):
        ip = client_ip(self)
        if not rate_allowed(ip):
            self.json_response(429, {"error": "Too many setup attempts. Wait before retrying."})
            return
        try:
            data = self.read_json()
            code = str(data.get("code", ""))
            if not valid_code(code):
                raise PermissionError("Invalid or sealed one-time setup code")

            if self.path == "/setup/install":
                status = read_status()
                if status.get("installed"):
                    self.json_response(200, {"message": "Worker is already installed. Use status to retrieve the control token before sealing."})
                    return
                if install_lock.locked():
                    self.json_response(202, {"message": "Installation is already running."})
                    return
                token = str(data.get("githubToken", "")).strip()
                wallet = str(data.get("creatorAddress", "")).strip()
                agent = str(data.get("agentName", "Replicatio-Prime")).strip()
                if not public_wallet(wallet):
                    raise ValueError("Enter a valid public EVM 0x wallet address")
                if len(agent) < 3 or len(agent) > 80:
                    raise ValueError("Agent name must contain 3-80 characters")
                thread = threading.Thread(target=install_worker, args=(token, wallet, agent), daemon=True)
                thread.start()
                self.json_response(202, {"message": "Installation started. This page will update automatically."})
                return

            if self.path == "/setup/status":
                status = read_status()
                out = {
                    "stage": status.get("stage"),
                    "progress": status.get("progress", 0),
                    "message": status.get("message", ""),
                    "installed": bool(status.get("installed")),
                    "workerUrl": status.get("workerUrl") or WORKER_URL,
                }
                if status.get("installed") and not status.get("sealed"):
                    token = read_control_token()
                    if token:
                        out["controlToken"] = token
                self.json_response(200, out)
                return

            if self.path == "/setup/ack":
                status = read_status()
                if not status.get("installed"):
                    raise ValueError("Installation is not complete")
                update_status(sealed=True, tokenAcknowledged=True, sealedAt=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
                self.json_response(200, {"sealed": True})
                return

            self.json_response(404, {"error": "not found"})
        except PermissionError as exc:
            self.json_response(403, {"error": str(exc)})
        except (ValueError, json.JSONDecodeError) as exc:
            self.json_response(400, {"error": str(exc)})
        except urllib.error.HTTPError as exc:
            self.json_response(400, {"error": "GitHub verification failed. Check that the token belongs to the owner and has read access only to Conway-Replicatio."})
        except Exception as exc:
            self.json_response(500, {"error": str(exc)})


if __name__ == "__main__":
    if len(SETUP_CODE) < 16 or not WORKER_HOST or not WORKER_URL:
        raise SystemExit("setup environment is incomplete")
    ROOT.mkdir(parents=True, exist_ok=True)
    if not STATUS_FILE.exists():
        update_status()
    print(f"[portal] listening on 127.0.0.1:9000 for {WORKER_URL}/setup/", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 9000), Handler).serve_forever()
