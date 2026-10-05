import collections
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from pitquant.analyzer import fundamental_v1 as FV
from pitquant.db.models_research import ResearchFeatureSnapshot
from pitquant.db.session import make_engine, make_session_factory
from pitquant.features.v0 import fundamentals as F
from pitquant.features.v0.engine import _debt, load_facts

s = make_session_factory(make_engine("sqlite:///data/pitquant.db"))()
j = json.loads(Path("docs/FIRST_ML_FOLD_AUDIT_PRE_FUND_RECOVERY.json").read_text())
miss = {}
for fold in j["folds"]:
    for role in ("TRAIN", "TEST"):
        for r in fold[role]["rows"]:
            if not r["family_reasons"]["PRICE"] and r["family_reasons"]["FUNDAMENTALS"] == [
                "FUNDAMENTALS_NOT_READY"
            ]:
                miss[r["security_id"], r["decision_at"]] = r
by = collections.defaultdict(list)
for r in miss.values():
    by[r["security_id"]].append(r)
output = []
for sid, rows in by.items():
    facts = load_facts(s, sid, datetime(2021, 10, 1, tzinfo=UTC))
    recovered = 0
    causes = collections.Counter()
    for row in rows:
        at = datetime.fromisoformat(row["decision_at"])
        vis = F.visible(facts, at)
        rev = FV._flow(vis, "revenue")
        ni = FV._flow(vis, "net_income")
        end = FV._end(rev)
        prior = (
            FV._flow(vis, "revenue", FV._years_before(end, 1))
            if end
            else F.Metric.missing("insufficient_history")
        )
        core = {
            "fund_net_margin": F.safe_div(ni, rev, "net margin", den_positive=True),
            "fund_revenue_yoy": FV._growth(rev, prior, "revenue yoy"),
            "fund_debt_to_assets": F.safe_div(
                _debt(vis), F.latest_instant(vis, "assets"), "debt / assets", den_positive=True
            ),
        }
        details = {
            k: {
                "value": v.value,
                "reason": v.reason,
                "formula": v.formula,
                "provenance": v.provenance,
                "available_at": v.available_at.isoformat() if v.available_at else None,
            }
            for k, v in core.items()
        }
        if all(v.value is not None for v in core.values()):
            recovered += 1
        causes.update((k, v.reason, v.formula) for k, v in core.items() if v.value is None)
        snap = s.scalars(
            select(ResearchFeatureSnapshot).where(
                ResearchFeatureSnapshot.security_id == sid,
                ResearchFeatureSnapshot.decision_at == at,
                ResearchFeatureSnapshot.feature_set_version == "research-features-v1-yahoo-v1",
            )
        ).one()
        output.append(
            {
                "security_id": sid,
                "issuer_id": row["issuer_id"],
                "decision_at": row["decision_at"],
                "ticker": snap.meta.get("ticker"),
                "core": details,
                "visible_facts": len(vis),
                "snapshot_status": snap.meta.get("fundamental_status"),
                "mandatory_source_features": {k: snap.features.get(k) for k in core},
            }
        )
    print(sid, len(rows), recovered, causes.most_common(3), flush=True)
Path("docs/FIRST_ML_FUNDAMENTAL_CORE_REPLAY.json").write_text(
    json.dumps(output, indent=2, sort_keys=True, default=str) + "\n"
)
