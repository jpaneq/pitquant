# ruff: noqa: E501
"""Read-only critical-window comparison; preserves the captured initial JSON."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from sqlalchemy import select

from pitquant.config.settings import get_settings
from pitquant.data.archive import ArchiveStore
from pitquant.db.models import RawSourceArchive, SecurityIdentifierEvidence, SP500Announcement
from pitquant.db.session import make_engine, make_session_factory
from pitquant.universe.sources.sp500_evidence import PARSER_VERSION

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs"


def load(name: str) -> dict:
    return json.loads((DOC / name).read_text())


def table(rows: list, headers: list[str]) -> str:
    return (
        "\n".join(
            [
                "| " + " | ".join(headers) + " |",
                "|" + "|".join("---" for _ in headers) + "|",
                *("| " + " | ".join(str(x).replace("|", "/") for x in row) + " |" for row in rows),
            ]
        )
        + "\n"
    )


def main() -> None:
    before = load("D02_CRITICAL_PATH_FIRST_ML.json")
    audit = load("D02_EXTENDED_AUDIT.json")
    readiness = load("DATA_READINESS_FIRST_ML.json")
    window = {m["decision_at"] for m in before["months"]}
    inside = [
        g
        for g in audit["gaps"]
        if g["blocks_membership"] and window.intersection(g["cohorts_blocked"])
    ]
    outside = [
        g
        for g in audit["gaps"]
        if g["blocks_membership"] and not window.intersection(g["cohorts_blocked"])
    ]
    remaining = {g["gap_id"] for g in inside}
    still_blocked_instruments = {(g["segment"], g.get("security_id")) for g in inside}
    reclassified = [
        g
        for g in before["blocking_cards"]
        if g["gap_id"] not in remaining
        and (g["segment"], g.get("security_id")) in still_blocked_instruments
    ]
    closed = [
        g
        for g in before["blocking_cards"]
        if g["gap_id"] not in remaining and g not in reclassified
    ]
    months = {m["month"]: m for m in readiness["monthly_cohorts"]}
    rows, monthly = [], []
    for old in before["months"]:
        new = months[old["month"]]
        cards = [g for g in inside if old["decision_at"] in g["cohorts_blocked"]]
        kinds = Counter(g["category"] for g in cards)
        weak = new["weak_identity_members"]
        entry = {
            "month": old["month"],
            "decision_at": old["decision_at"],
            "before_status": old["status"],
            "after_status": new["status"],
            "membership_ready": new["membership_ready"],
            "blocking_cards": len(cards),
            "gap_ids": [g["gap_id"] for g in cards],
            "categories": dict(kinds),
            "weak_identity_members": weak,
            "identity_assessment_complete": new["membership_ready"],
            "minimum_action": "None"
            if new["status"] == "READY"
            else (
                "Official class-preserving identity evidence for listed weak members"
                if weak
                else "Close the listed official-event cards and replay; identity set cannot yet be fully certified"
            ),
        }
        monthly.append(entry)
        rows.append(
            [
                entry["month"],
                entry["after_status"],
                len(cards),
                kinds["PRIMARY_EVENT_MISSING"],
                kinds["SECURITY_IDENTITY_ONLY"],
                kinds["MONTHLY_DATE_AMBIGUITY"],
                kinds["PRIMARY_DELTA_UNEXPLAINED"],
                len(weak) if new["membership_ready"] else "not fully reconstructible",
                entry["minimum_action"],
            ]
        )
    cfg = get_settings()
    sources, weak_proofs = [], []
    store = ArchiveStore(ROOT / cfg.archive.root)
    critical_weak_ids = {
        "1f5bf423-0fae-4ed7-8eaf-9090a7676997",
        "38bf85dd-d63a-40aa-a42d-1269ecbb8cad",
        "6fa036f9-b3f6-41e3-a943-b4009051c02b",
        "9a3b66a2-829d-489f-93f2-7b1e87f540dc",
        "c69556ba-d94b-40ce-8f16-e755ed96674d",
        "ccaf4880-ad73-42a9-8c3a-acff8aca5275",
        "d0faf05d-2172-4ea7-9448-44ae828556d3",
        "d2ce86fb-10d0-40e7-9dd0-9fe220d7a0c9",
        "dff57c93-452d-40bc-b6cc-bb1835281ac5",
        "65082008-9521-4c8a-bf05-ff362b047e14",
    }
    import hashlib

    with make_session_factory(make_engine(cfg.database.url))() as session:
        for ann in session.scalars(
            select(SP500Announcement).where(SP500Announcement.parser_version == PARSER_VERSION)
        ):
            if (
                not ann.effective_at
                or not "2015-09" <= ann.effective_at.strftime("%Y-%m") <= "2017-09"
            ):
                continue
            archive = session.get_one(RawSourceArchive, ann.archive_id)
            if hashlib.sha256(store.get(archive.sha256)).hexdigest() != ann.source_sha256:
                raise ValueError("Membership archive integrity failure")
            sources.append(
                {
                    "announcement_id": ann.announcement_row_id,
                    "url": ann.source_url,
                    "sha256": ann.source_sha256,
                    "archive_id": ann.archive_id,
                    "retrieved_at": str(archive.retrieved_at),
                    "announced_at": str(ann.announcement_at),
                    "stated_change_date": str(ann.stated_change_date),
                    "effective_at": str(ann.effective_at),
                    "added_name": ann.added_name,
                    "removed_name": ann.removed_name,
                    "added_ticker": ann.added_ticker,
                    "removed_ticker": ann.removed_ticker,
                    "parser_version": ann.parser_version,
                    "source_tier": ann.source_tier,
                    "excerpt": ann.excerpt,
                }
            )
        for evidence in session.scalars(
            select(SecurityIdentifierEvidence).where(
                SecurityIdentifierEvidence.security_id.in_(critical_weak_ids),
                SecurityIdentifierEvidence.kind == "OFFICIAL",
            )
        ):
            weak_proofs.append(
                {
                    "security_id": evidence.security_id,
                    "type": evidence.id_type,
                    "value": evidence.value,
                    "observed_on": str(evidence.observed_on),
                    "source_hash": evidence.source_sha256,
                    "archive_id": evidence.archive_id,
                    "url": evidence.source_url,
                    "original_and_resolution": evidence.excerpt,
                }
            )
    result = {
        "initial_head": before["initial_head"],
        "scope": before["critical_window"],
        "before": {
            "ready_months": 60,
            "longest_run": 60,
            "folds": 0,
            "cards": len(before["blocking_cards"]),
            "categories": dict(Counter(g["category"] for g in before["blocking_cards"])),
        },
        "after": readiness["d02"],
        "resolved_months": [m["month"] for m in monthly if m["after_status"] == "READY"],
        "closed_original_cards": closed,
        "reclassified_original_cards_still_blocked": reclassified,
        "resolved_categories": dict(Counter(g["category"] for g in closed)),
        "current_months_descending": monthly,
        "inside_critical_cards": inside,
        "outside_critical_cards": outside,
        "folds": readiness["folds"],
        "gates": readiness["gates"],
        "membership_provenance": sources,
        "critical_weak_identity_proofs": weak_proofs,
        "source_attempts": load("D02_CRITICAL_SOURCE_ATTEMPTS.json"),
        "stop_reason": "Not achieved: official Under Armour Class C index-effective notice still unavailable in retrieved evidence; next chronological segment remains blocked. This does not prove no document exists.",
        "required_securities": 100,
        "methodology": "User approved designing a later statistical replacement of the global-100 gate; no replacement threshold applied. Calendar folds are not proof of mature labels or model eligibility.",
    }
    (DOC / "D02_CRITICAL_PATH_RESULT.json").write_text(
        json.dumps(result, indent=2, default=str) + "\n"
    )
    d = readiness["d02"]
    text = "# D02 critical path to first ML\n\n"
    text += f"**Not achieved.** Usable READY months: 60 → {d['ready_months']}; longest usable run: 60 → {d['longest_run']}/85; calendar folds: 0 → {d['feasible_folds']}/3. Membership-only ready months: {d['membership_ready_months']}. No training.\n\n"
    text += "Scope: 2015-09 through 2017-09, processed newest first. Shared segment proofs closed six-month blocks; the chronology stops at the still-blocked 2016-09 decision. Original baseline rows and all 93 original cards are preserved unchanged in `D02_CRITICAL_PATH_FIRST_ML.json`; current comparison and exact source provenance are in `D02_CRITICAL_PATH_RESULT.json`. Raw anchors remain unchanged.\n\n"
    text += table(
        [
            ["Original critical cards", 93],
            ["Original cards closed", len(closed)],
            ["Current inside-critical membership cards", len(inside)],
            ["Outside-critical membership cards (inventoried, not cleanup target)", len(outside)],
            ["Current global weak identities", d["weak_identity_securities"]],
        ],
        ["Measure", "Count"],
    )
    text += "\n## Current monthly table, descending\n\n" + table(
        rows,
        [
            "Month",
            "Status",
            "Cards",
            "Events",
            "Identity cards",
            "Ambiguities",
            "Conflicts",
            "Weak instruments",
            "Minimum action",
        ],
    )
    text += "\nA blocked month has no fully certified member set: its weak-instrument count is unknown, not zero. Identity cards are distinct from weak identities within a reconstructed member set. Card totals count instrument legs, not independent corporate transactions.\n\n"
    text += "## Reviewed closures\n\nOne Broadcom Ltd card changed from contradiction to missing addition and remains blocked; its changed gap ID is not counted as resolved.\n\nDated SEC transactions distinguish Dominion, Tesoro, CSC/DXC, Dow/DowDuPont, GGP, L-3, FMC/TechnipFMC, Alcoa/Arconic, DaVita, McGraw/S&P Global, XL and Tyco/JCI. Ratios are specific to the predecessor: CSC and Dow 1:1, FMC 1:1, XL 1:1, L-3 1:1, Tyco 0.955:1; RTN, DuPont and old Johnson Controls are separate legs. Sources, header CIK/accession checks, classes, CUSIPs/ISINs, legal/trading dates, precision and hashes are in `D02_CRITICAL_IDENTITY_RESOLUTIONS.json`.\n\n"
    text += "Parser fixes retain Nemours' final s, resolve exact same-release full names, accept 'at the open', and admit an index-less pair only if the exact S&P 500 summary table confirms both legs. A pretraded N-30D pair is adjusted only when the same official next-session pair supports both sides. Two document-specific BR artifacts preserve explicit class A. Closed SEC issuer abbreviations resolve only exact names and compatible explicit classes in every anchor quarter; a mismatch remains blocked. No issuer, ticker or spelling similarity merges securities.\n\n"
    text += "**Time precision:** L-3 and Alcoa filings state local times without a timezone. The stored UTC values are monthly reconstruction boundaries, not verified legal UTC instants; reviewed precision notes supersede the initial ET wording retained in immutable local link notes. Neither uncertain instant can change the first NYSE monthly decision here. Intraday use would require explicit timezone evidence. Alcoa's reverse split and spin-off remain separate from the name/identifier event; no research return remapping was performed.\n\n"
    text += "## Remaining critical cards\n\n" + table(
        [
            [g["gap_id"], g["segment"], g["security"], g["category"], g["document_required"]]
            for g in inside
        ],
        ["Gap ID", "Segment", "Instrument", "Category", "Official proof required"],
    )
    text += "\n## Honest stopping condition and minimum next action\n\nThe newest remaining segment 2016-03→09 is blocked by Under Armour Class C. The SEC annual filing proves distribution April 7 and initial UA.C listing April 8, but not the index-effective date. Targeted searches of official S&P press/indexnews sources retrieved no sufficient dated Class C inclusion notice. Secondary dates remain discovery only, and issuer evidence cannot substitute for S&P membership. `D02_CRITICAL_SOURCE_ATTEMPTS.json` records the attempts and insufficient official document with its hash. Obtain that notice and replay this segment before moving to 2015-09→2016-03 and the September 2015 decision. Do not infer absence of an official document from search misses.\n\n"
    text += "## Exact current calendar folds\n\n" + table(
        [
            [
                f["index"],
                f["train_start"] + ".." + f["train_end"],
                f["train_months"],
                f["excluded_decision_start"] + ".." + f["excluded_decision_end"],
                f["embargo_start"] + ".." + f["embargo_end"],
                f["test_start"] + ".." + f["test_end"],
            ]
            for f in readiness["folds"]
        ],
        ["Fold", "Train", "N train", "Excluded decisions", "Embargo", "Test"],
    )
    text += "\nFrozen inequality: train decision + H12 + embargo1 <= test start. Inclusive endpoints yield 37 training decision months in the first fold and 12 excluded decision months; the embargo lies within that excluded span. This documents the existing contract without changing it. Calendar feasibility alone does not certify mature 12M labels; holdout/OOT remain sealed and no labels/features are rebuilt.\n\n"
    text += "## Gate matrix\n\n" + table(
        [[k, v["status"], v["actual"]] for k, v in readiness["gates"].items()],
        ["Gate", "Status", "Evidence"],
    )
    text += "\nRequired securities=100 unchanged. The user has approved the *later methodological design* of a statistical coverage gate; no 100→51 reduction or substitute threshold is applied. XOM/RTX/GOOGL/GE research-series bindings remain PARTIAL, with their separate issues unchanged; see `FIRST_ML_SECURITY_IDENTITY.json`. Full source originals stay in the content-addressed archive; all new proof checks use pre-holdout historical sources.\n\n"
    text += "Reproduce from repository root with the explicit project DB: `apply_d02_critical_identity.py` (runtime SEC contact), `apply_d02_document_breaks.py`, `apply_d02_critical_weak_identity.py`, `ingest_sp500_evidence.py --offline`, `build_sp500_anchor_graph.py`, `gen_d02_extended_audit.py`, `gen_data_readiness_first_ml.py`, `gen_d02_critical_provenance.py`, `gen_d02_critical_report.py`. No BTC, champion/master, model training or deployment is involved.\n"
    (DOC / "D02_CRITICAL_PATH_FIRST_ML.md").write_text(text)


if __name__ == "__main__":
    main()
