#!/usr/bin/env python3
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.neural_crm import AutonomyMode, NeuralCRMEngine  # noqa: E402
from intelligence.neural_crm.policy import ActionClass, DecisionPolicy  # noqa: E402


TODAY = date(2026, 7, 21)


def snapshot(**lead_overrides):
    lead = {
        "Lead ID": "LEAD-NEURAL-001",
        "Company": "Synthetic Neural Export Lab",
        "Status": "Qualified",
        "Fit Score": 84,
        "Service Interest": "IVA",
        "Company ID": "COM-NEURAL-001",
        "Contact ID": "CON-NEURAL-001",
        "Opportunity ID": "",
        "Consent Basis": "Assessment consent recorded",
        "Last Contact": "2026-07-18",
        "Next Action Date": "2026-07-21",
        "Next Action": "Review discovery evidence",
        "Owner": "Synthetic Owner",
        "Notes": "International website is credible but unclear to export buyers.",
    }
    lead.update(lead_overrides)
    return {
        "lead": lead,
        "company": {
            "Company ID": "COM-NEURAL-001",
            "Website": "https://synthetic-neural.example.test",
            "Sector": "Industrial simulation",
            "International Fit": 82,
            "Notes": "Synthetic test organisation only.",
        },
        "contact": {
            "Contact ID": "CON-NEURAL-001",
            "Company ID": "COM-NEURAL-001",
            "Email": "private-person@example.test",
            "Consent Status": "Assessment consent recorded",
            "Relationship Strength": 65,
            "Last Contact": "2026-07-18",
        },
        "service": {
            "code": "IVA",
            "status": "active",
            "price_eur": 149,
            "delivery_days": 3,
            "automation_target_pct": 55,
            "name": "International Visibility Audit",
        },
        "activities": [
            {
                "Date": "2026-07-12",
                "Activity Type": "Email",
                "Channel": "Email",
                "Summary": "Sent requested diagnostic questions",
                "Outcome": "Replied with useful detail",
                "Duration Minutes": 18,
            },
            {
                "Date": "2026-07-18",
                "Activity Type": "Discovery call",
                "Channel": "Video",
                "Summary": "Discussed international website friction",
                "Outcome": "Interested in visibility audit",
                "Duration Minutes": 35,
            },
        ],
    }


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def run():
    evidence = []

    def case(name, function):
        function()
        evidence.append({"case": name, "result": "passed"})

    def shadow_plan():
        result = NeuralCRMEngine().evaluate(snapshot(), today=TODAY)
        prediction = result["prediction"]
        for key in ("conversion_probability", "relationship_strength", "urgency_probability", "churn_risk", "confidence", "uncertainty"):
            require(0.0 <= prediction[key] <= 1.0, f"{key} outside probability range")
        require(prediction["ensemble_size"] == 7, "expected seven-member multidimensional ensemble")
        require(len(prediction["action_probabilities"]) == 5, "next-action distribution incomplete")
        require(result["eligibility"]["eligible"], "qualified synthetic lead should be eligible")
        require(result["opportunity_plan"]["Value €"] == 149.0, "price must derive from canonical service")
        require(result["execution"]["action"] == "shadow_record", "default mode must remain shadow")
        require(not result["execution"]["mutation_permitted"], "shadow mode must not mutate")

    case("qualified lead produces multidimensional neural shadow opportunity plan", shadow_plan)

    def deterministic():
        engine = NeuralCRMEngine()
        first = engine.evaluate(snapshot(), today=TODAY)
        second = engine.evaluate(snapshot(), today=TODAY)
        require(first["cycle_id"] == second["cycle_id"], "cycle ID is not deterministic")
        require(first["opportunity_plan"]["Opportunity ID"] == second["opportunity_plan"]["Opportunity ID"], "opportunity ID is not deterministic")
        require(first["prediction"] == second["prediction"], "shadow neural inference is not deterministic")

    case("deterministic model and record identities", deterministic)

    def alias_normalisation():
        item = snapshot(**{"Service Interest": "OSP"})
        item["service"]["code"] = "OSP"
        item["service"]["price_eur"] = 249
        result = NeuralCRMEngine().evaluate(item, today=TODAY)
        require(result["service_code"] == "IOP", "legacy OSP alias was not canonicalised")
        require(any("legacy_service_alias:OSP->IOP" == warning for warning in result["warnings"]), "alias provenance warning missing")
        require(result["opportunity_plan"]["Service Code"] == "IOP", "opportunity used legacy service code")

    case("legacy CRM service alias normalises to canonical IOP", alias_normalisation)

    def ineligible_status():
        result = NeuralCRMEngine().evaluate(snapshot(**{"Status": "New"}), today=TODAY)
        require(not result["eligibility"]["eligible"], "unqualified lead became eligible")
        require("lead_status_not_qualified" in result["eligibility"]["reasons"], "status rejection reason missing")
        require(result["opportunity_plan"] is None, "ineligible lead received opportunity plan")
        require(result["execution"]["action"] == "hold_ineligible", "ineligible lead not held")

    case("non-qualified lead is held", ineligible_status)

    def insufficient_fit():
        result = NeuralCRMEngine().evaluate(snapshot(**{"Fit Score": 40}), today=TODAY)
        require("fit_score_below_minimum" in result["eligibility"]["reasons"], "fit threshold was not enforced")
        require(result["opportunity_plan"] is None, "low-fit lead received opportunity plan")

    case("minimum fit threshold enforced", insufficient_fit)

    def inactive_service():
        item = snapshot()
        item["service"]["status"] = "hidden_until_sale"
        result = NeuralCRMEngine().evaluate(item, today=TODAY)
        require("service_not_active" in result["eligibility"]["reasons"], "inactive service was not rejected")
        require(result["opportunity_plan"] is None, "inactive service received opportunity plan")

    case("inactive service blocked", inactive_service)

    def duplicate_preserved():
        existing = [{
            "Opportunity ID": "OPP-MANUAL-001",
            "Service Code": "IVA",
            "Notes": "lead_id=LEAD-NEURAL-001; human_curated=true",
            "Value €": 999,
        }]
        result = NeuralCRMEngine().evaluate(snapshot(), existing_opportunities=existing, today=TODAY)
        require(result["existing_opportunity"]["Opportunity ID"] == "OPP-MANUAL-001", "existing opportunity was not found")
        require(result["execution"]["action"] == "duplicate_existing_opportunity", "duplicate did not stop creation")
        require(not result["execution"]["mutation_permitted"], "duplicate path permitted mutation")
        require("existing_opportunity_preserved" in result["warnings"], "preservation warning missing")

    case("existing human-curated opportunity preserved", duplicate_preserved)

    def pii_not_in_ledger():
        result = NeuralCRMEngine().evaluate(snapshot(), today=TODAY)
        ledger = json.dumps(result["evidence_ledger"], sort_keys=True)
        require("private-person@example.test" not in ledger, "email leaked into neural evidence ledger")
        require("Synthetic Neural Export Lab" not in ledger, "company name leaked into neural evidence ledger")
        require(len(result["evidence_ledger"]["entries"]) == 6, "cognitive colony evidence is incomplete")
        require(len(result["evidence_ledger"]["ledger_digest"]) == 64, "ledger digest is invalid")

    case("evidence ledger is provenance-bearing and PII-minimised", pii_not_in_ledger)

    def external_actions_blocked():
        policy = DecisionPolicy(AutonomyMode.BOUNDED_AUTO)
        decision = policy.decide(ActionClass.EXTERNAL_COMMUNICATION, 0.99, 0.01, human_approved=False, synthetic_only=False)
        require(not decision.permitted, "external communication bypassed human custody")
        require(decision.execution == "request_approval", "external communication did not request approval")
        approved = policy.decide(ActionClass.EXTERNAL_COMMUNICATION, 0.99, 0.01, human_approved=True, synthetic_only=False)
        require(approved.permitted, "explicitly approved external action remained blocked")
        require(approved.requires_human, "approval custody was not recorded")

    case("external communication remains under human custody", external_actions_blocked)

    def bounded_auto_is_confidence_gated():
        result = NeuralCRMEngine(mode=AutonomyMode.BOUNDED_AUTO).evaluate(snapshot(), today=TODAY)
        if result["execution"]["mutation_permitted"]:
            require(result["prediction"]["confidence"] >= result["execution"]["confidence_threshold"], "auto mutation below confidence threshold")
            require(result["prediction"]["uncertainty"] <= result["execution"]["uncertainty_ceiling"], "auto mutation above uncertainty ceiling")
            require(result["execution"]["action"] == "execute_with_audit", "bounded autonomy used wrong execution mode")
        else:
            require(result["execution"]["action"] == "request_review", "confidence-gated hold did not request review")

    case("bounded internal autonomy is confidence and uncertainty gated", bounded_auto_is_confidence_gated)

    print(json.dumps({"ok": True, "model": "neural-crm-shadow-v0.1-multidimensional-fabric", "tests": evidence}, indent=2))


if __name__ == "__main__":
    run()
