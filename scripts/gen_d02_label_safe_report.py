# ruff: noqa: E501
"""Read-only V2 operational critical path; old iteration remains a frozen baseline."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs"


def table(rows, headers):
    return (
        "\n".join(
            [
                "| " + " | ".join(headers) + " |",
                "|" + "|".join("---" for _ in headers) + "|",
                *("| " + " | ".join(str(v).replace("|", "/") for v in r) + " |" for r in rows),
            ]
        )
        + "\n"
    )


def main():
    readiness = json.loads((DOC / "DATA_READINESS_FIRST_ML.json").read_text())
    extended = json.loads((DOC / "D02_EXTENDED_AUDIT.json").read_text())
    baseline = json.loads((DOC / "D02_CRITICAL_PATH_RESULT_PRE_LABEL_SAFE_V2.json").read_text())
    history = readiness["required_history"]
    folds = readiness["folds"]
    months = [
        m
        for m in readiness["monthly_cohorts"]
        if history["minimum_ready_history_start"]
        <= m["month"]
        <= history["last_required_dev_month"]
    ]
    dates = {m["date"] for m in months}
    inside = [
        g
        for g in extended["gaps"]
        if g["blocks_membership"] and dates.intersection(g["cohorts_blocked"])
    ]
    inside = [
        dict(
            g,
            document_required=g["document_required"].replace(
                "Dated S&P release proving", "Dated official S&P index notice/history/file proving"
            ),
        )
        for g in inside
    ]
    outside = [
        g
        for g in extended["gaps"]
        if g["blocks_membership"] and not dates.intersection(g["cohorts_blocked"])
    ]
    monthly = []
    for m in reversed(months):
        cards = [g for g in inside if m["date"] in g["cohorts_blocked"]]
        counts = Counter(g["category"] for g in cards)
        roles = []
        for f in folds:
            if f["train_start"] <= m["month"] <= f["train_end"]:
                roles.append(f"F{f['index'] + 1}:TRAIN")
            elif f["test_start"] <= m["month"] <= f["test_end"]:
                roles.append(f"F{f['index'] + 1}:TEST")
            elif f["excluded_decision_start"] <= m["month"] <= f["excluded_decision_end"]:
                roles.append(f"F{f['index'] + 1}:PURGE/EMBARGO_CONTINUITY")
        minimum = (
            "NONE"
            if m["status"] == "READY"
            else (
                "Official class-preserving identity evidence for "
                + ", ".join(m["weak_identity_members"])
                if m["weak_identity_members"]
                else "; ".join(sorted({g["document_required"] for g in cards}))
                or m["blocking_reason"]
            )
        )
        monthly.append(
            dict(
                month=m["month"],
                decision_at=m["date"],
                required_by_fold=roles,
                status=m["status"],
                blocking_cards=len(cards),
                gap_ids=sorted(g["gap_id"] for g in cards),
                events=counts["PRIMARY_EVENT_MISSING"],
                identities=counts["SECURITY_IDENTITY_ONLY"],
                ambiguities=counts["MONTHLY_DATE_AMBIGUITY"],
                conflicts=counts["PRIMARY_DELTA_UNEXPLAINED"],
                minimum_resolution=minimum,
            )
        )
    blocked = [m for m in monthly if m["status"] != "READY"]
    first = blocked[0] if blocked else None
    result = dict(
        version="d02-label-safe-critical-path-v2",
        initial_head="a47228d7534771fc44cc446b9654a8719d7ff7d7",
        previous_iteration_baseline_file="D02_CRITICAL_PATH_RESULT_PRE_LABEL_SAFE_V2.json",
        original_critical_baseline_file="D02_CRITICAL_PATH_FIRST_ML.json",
        head_trace=json.loads((DOC / "CLAUDE_HEAD_TRACE.json").read_text()),
        required_history=history,
        before=dict(
            ready_months=72,
            total_months=141,
            global_streak=72,
            available_calendar_folds=1,
            label_safe_folds=0,
        ),
        after=readiness["d02"],
        required_months=len(months),
        required_months_blocked=len(blocked),
        membership_cards=len(inside),
        categories=dict(Counter(g["category"] for g in inside)),
        first_blocked_month=first,
        newly_resolved_months=[],
        newly_resolved_cards=[],
        current_months_descending=monthly,
        inside_critical_cards=inside,
        outside_critical_cards=outside,
        folds=folds,
        fold_readiness=readiness["fold_readiness"],
        gates=readiness["gates"],
        source_attempts=json.loads((DOC / "D02_CRITICAL_SOURCE_ATTEMPTS.json").read_text()),
        under_armour_evidence_matrix=json.loads(
            (DOC / "D02_UNDER_ARMOUR_EVIDENCE_MATRIX.json").read_text()
        ),
        membership_provenance=baseline["membership_provenance"],
        critical_weak_identity_proofs=baseline["critical_weak_identity_proofs"],
        required_securities=100,
        models_trained=False,
        stop_reason="OFFICIAL_INDEX_DATE_UNVERIFIED: Under Armour Class C blocks the newest required month. No clean-up outside the derived critical path; alternative official index notices/history are accepted, corporate dates are not index dates.",
    )
    (DOC / "D02_CRITICAL_PATH_RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
    text = "# D02 — label-safe critical path V2\n\n"
    text += f"**BLOCKED.** {len(blocked)} required months remain unresolved; first blocker **{first['month'] if first else 'NONE'}**. Global READY remains 72/141 (72-month run), but only {readiness['d02']['required_months_ready']}/85 of the correctly positioned history is READY. No model trained.\n\n"
    text += "## Reproducible temporal derivation\n\n" + table(
        [[k, v] for k, v in history.items()], ["Parameter", "Derived value"]
    )
    text += "\nThe latest monthly XNYS open whose nominal H12 endpoint precedes holdout is derived by walking market months backwards. Both the security and SPY use the previous closed XNYS session at the target instant; maturity uses the existing one-hour lag. Nominal horizon, not merely the earlier exit close, is the frozen sealing rule. No prices or outcomes in holdout/OOT are inspected.\n\n"
    text += "The frozen inclusive calendar requires 36+12+1+12+2×12=85 continuous decision months, positioned **2014-09..2021-09**. The first fold retains 37 calendar TRAIN months, as in the existing contract. The missing extension is **2014-09..2016-09: 25 months**. The 2016-10..2021-09 portion contributes 60 usable months; the extra READY months through 2022-09 do not make H12 TEST labels admissible. Membership is required at decisions; outcome prices extend to 2022-09 without requiring later decision cohorts.\n\n"
    text += "## Three latest target calendar folds\n\n" + table(
        [
            [
                f["index"] + 1,
                f["train_start"] + ".." + f["train_end"],
                f["excluded_decision_start"] + ".." + f["excluded_decision_end"],
                f["embargo_start"] + ".." + f["embargo_end"],
                f["test_start"] + ".." + f["test_end"],
            ]
            for f in folds
        ],
        ["Fold", "TRAIN", "Purge/excluded decisions", "Embargo", "TEST"],
    )
    text += "\nThese are three structurally valid **target** calendars, not three ready historical datasets. The prior READY-run generator still yields one calendar (TEST 2020-11..2021-10), which is not label-safe; shifting only that single run does not fill the missing TRAIN history.\n\n"
    text += "## Calendar vs labels vs coverage\n\nCALENDAR_FOLD validates dates. LABEL_SAFE_FOLD certifies a complete required membership/identity history, at least the contracted 36 TRAIN decision months with labels available at fit, and all twelve TEST months with valid H12 outcomes. Individual absent rows are reported; no per-security or per-issuer sample-size threshold is used. ML_ELIGIBLE_FOLD adds the future statistical coverage contract and stays NOT_YET_EVALUATED_BLOCKED_BY_COVERAGE. `required_securities=100` is unchanged and cannot decide label safety. ADR-0055 V2 supersedes its earlier conflation with trainability.\n\n"
    text += table(
        [
            [
                f["index"] + 1,
                f["calendar_valid"],
                f["test_label_safe"],
                f["label_safe"],
                f["TRAIN"]["eligible_rows"],
                f["TEST"]["eligible_rows"],
                f["TEST"]["eligible_securities"],
                f["TEST"]["eligible_issuers"],
                ", ".join(f["blocking_reasons"]),
            ]
            for f in readiness["fold_readiness"]["folds"]
        ],
        [
            "Fold",
            "Calendar valid",
            "TEST label safe",
            "Full fold label safe",
            "TRAIN eligible",
            "TEST eligible",
            "Securities",
            "Issuers",
            "Blocking reasons",
        ],
    )
    text += "\nTEST outcomes already span all twelve months in each intended fold. Full-fold certification is blocked by the missing earlier membership history and insufficient verified TRAIN months. Source values remain immutable; no labels/features were built. Every decision window, availability cutoff, actual exit, maturity and exclusion is in `FIRST_ML_FOLD_AUDIT.json`.\n\n"
    text += "## Required monthly path (newest first)\n\n" + table(
        [
            [
                m["month"],
                ", ".join(m["required_by_fold"]),
                m["status"],
                m["blocking_cards"],
                m["events"],
                m["identities"],
                m["ambiguities"],
                m["conflicts"],
                m["minimum_resolution"],
            ]
            for m in monthly
        ],
        [
            "Month",
            "Required by fold",
            "Status",
            "Cards",
            "Events",
            "Identities",
            "Ambiguities",
            "Conflicts",
            "Minimum resolution",
        ],
    )
    text += f"\nDistinct in-path cards: **{len(inside)}**, categories {dict(Counter(g['category'] for g in inside))}. Full gap IDs, official anchor references and resolution requirements remain in the result JSON and `D02_EXTENDED_AUDIT.json`; {len(outside)} cards are outside this path and are not clean-up targets.\n\n"
    text += "## Under Armour and chronological stop\n\n**OFFICIAL_INDEX_DATE_UNVERIFIED.** Distribution 2016-04-07 and regular-way listing 2016-04-08 are proved; index inclusion is not. Class A and C, their CUSIPs and recycled ticker histories remain separate. Official S&P announcements, archived pages, constituent notices/history and index files are acceptable formats. Searches, historical archive URLs, temporal range and failure status are in `D02_CRITICAL_SOURCE_ATTEMPTS.json`; SEC/OCC alternative evidence and hashes are in the evidence matrix. The minimum missing proof is an official dated index record directly establishing Class C inclusion and its effective date. No secondary date is promoted. Stop before resolving earlier months until this newest required blocker closes.\n\n"
    text += "## Claude trace and unchanged scope\n\n`CLAUDE_HEAD_TRACE.md/.json` audits both intervening commits and all eighteen paths: no D02/fold/target/holdout/readiness contract changed. Existing interface additions are retained. L-3/Alcoa remain TIME_PRECISION_NOT_MATERIAL_FOR_MONTHLY_MEMBERSHIP with unknown legal timezone; XOM/RTX/GOOGL/GE and Broadcom are inventoried only when they block this path. No BTC, global markets, features, models, champion/master or coverage-threshold changes.\n\n"
    text += "## Gates\n\n" + table(
        [[k, v["status"], v["actual"]] for k, v in readiness["gates"].items()],
        ["Gate", "Status", "Actual"],
    )
    text += "\nReproduce offline with the explicit project DB: `scripts/gen_data_readiness_first_ml.py`, then `scripts/gen_d02_label_safe_report.py` (legacy `gen_d02_critical_report.py` delegates here). Original pre-V2 reports and source provenance are retained in the baseline file; original 93 cards are not rewritten.\n"
    (DOC / "D02_CRITICAL_PATH_FIRST_ML.md").write_text(text)


if __name__ == "__main__":
    main()
