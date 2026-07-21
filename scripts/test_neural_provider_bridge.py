#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.neural_crm.bridge import NeuralProviderBridge  # noqa: E402


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def run_node(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(ROOT / "scripts" / "neural_bridge_harness.js"), *args],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def run() -> None:
    evidence = []

    def case(name, function):
        function()
        evidence.append({"case": name, "result": "passed"})

    def apps_script_core():
        result = json.loads(run_node().stdout)
        require(result["ok"] is True, "Apps Script core harness failed")
        require(len(result["tests"]) == 7, "Apps Script test count changed")

    case("Apps Script package core passes seven cases", apps_script_core)

    package = json.loads(run_node("--emit").stdout)
    bridge = NeuralProviderBridge()

    def cross_runtime_digest():
        validated = bridge.validate(package)
        require(validated.feature_digest == package["feature_digest"], "JavaScript/Python feature digest mismatch")
        require(validated.service_code == "IOP", "canonical service code lost")
        require(validated.service_price_eur == 249.0, "service price lost")

    case("JavaScript package validates in Python", cross_runtime_digest)

    def neural_decision():
        decision = bridge.infer(package)
        require(decision["decision_version"] == "neural-provider-decision-v1", "decision version wrong")
        require(decision["package_id"] == package["package_id"], "package linkage wrong")
        require(decision["feature_digest"] == package["feature_digest"], "feature linkage wrong")
        require(len(decision["decision_digest"]) == 64, "decision digest invalid")
        require(decision["proposed_internal_action"]["value_eur"] == 249.0, "neural decision changed canonical price")
        require(decision["execution_policy"]["mutation_permitted"] is False, "shadow decision permitted mutation")
        require(decision["execution_policy"]["external_communication_permitted"] is False, "shadow decision permitted communication")

    case("neural bridge returns evidence-safe shadow decision", neural_decision)

    def deterministic():
        first = bridge.infer(package)
        second = bridge.infer(package)
        require(first == second, "neural provider decision is not deterministic")

    case("cross-runtime decision is deterministic", deterministic)

    def tampering_blocked():
        tampered = json.loads(json.dumps(package))
        tampered["features"]["tabular"][0] = 0.01
        try:
            bridge.validate(tampered)
        except ValueError as error:
            require(str(error) == "feature_digest_mismatch", "unexpected tamper error")
        else:
            raise AssertionError("tampered package was accepted")

    case("feature tampering is detected", tampering_blocked)

    def pii_blocked():
        unsafe = json.loads(json.dumps(package))
        unsafe["email"] = "private@example.test"
        try:
            bridge.validate(unsafe)
        except ValueError as error:
            require(str(error) == "pii_or_free_text_field_detected", "unexpected PII error")
        else:
            raise AssertionError("PII-bearing package was accepted")

    case("PII-bearing package is rejected", pii_blocked)

    def production_gate_blocked():
        unsafe = json.loads(json.dumps(package))
        unsafe["synthetic_only"] = False
        try:
            bridge.validate(unsafe)
        except ValueError as error:
            require(str(error) == "synthetic_gate_closed", "unexpected synthetic-gate error")
        else:
            raise AssertionError("production-like package was accepted")

    case("synthetic provider gate is fail-closed", production_gate_blocked)

    def cli_round_trip():
        completed = subprocess.run(
            ["python", str(ROOT / "scripts" / "run_neural_shadow.py"), "-"],
            cwd=ROOT,
            input=json.dumps(package),
            check=True,
            text=True,
            capture_output=True,
        )
        decision = json.loads(completed.stdout)
        require(decision["package_id"] == package["package_id"], "CLI output lost package linkage")
        require(decision["execution_policy"]["mode"] == "shadow", "CLI did not remain shadow")

    case("CLI performs PII-free shadow round trip", cli_round_trip)

    print(json.dumps({"ok": True, "tests": evidence}, indent=2))


if __name__ == "__main__":
    run()
