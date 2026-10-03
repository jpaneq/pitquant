"""Generate docs/DATA_MODEL.md from the SQLAlchemy metadata (single source of truth)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from pitquant.db.base import Base
from pitquant.db.models import IMMUTABLE_TABLES

GROUPS = {
    "Procedencia y calidad": [
        "data_sources",
        "raw_records",
        "raw_source_archive",
        "data_quality_issues",
    ],
    "Security Master": [
        "issuers",
        "securities",
        "provider_keys",
        "ticker_history",
        "identifier_history",
        "issuer_identifiers",
        "sector_classification",
    ],
    "Identidad (ADR-0020)": [
        "security_identity_snapshots",
        "official_code_isin_evidence",
        "official_isin_transitions",
        "security_identifier_evidence",
        "sp500_discovery_rows",
        "sp500_announcements",
        "sp500_membership_events",
        "sp500_anchors",
        "sp500_anchor_members",
        "sp500_anchor_crosschecks",
        "sp500_membership_segments",
        "security_ticker_alias",
        "sec_13f_list_entries",
        "security_succession",
        "simulations",
        "simulation_observations",
        "simulation_outcomes",
        "simulation_events",
        "simulation_counterfactuals",
        "simulation_postmortems",
        "research_hypotheses",
        "index_anchor_snapshots",
        "index_current_anchors",
        "security_profiles",
        "feature_set_versions",
        "label_definitions",
        "model_configs",
        "dataset_versions",
        "research_experiments",
        "research_folds",
        "research_predictions",
        "realized_outcomes",
        "metric_sets",
        "champion_challenger_comparisons",
        "identity_resolution_runs",
        "membership_identity_segments",
    ],
    "Universo": ["index_events", "membership_builds", "index_membership"],
    "Mercado": [
        "prices",
        "provider_adjusted_prices",
        "corporate_action_events",
        "corporate_action_ingestions",
        "corporate_actions",
        "dividends",
        "benchmarks",
        "benchmark_levels",
    ],
    "Fundamentales, estimaciones y macro": [
        "financial_statements",
        "sec_filings",
        "cnmv_filings",
        "fundamental_facts",
        "analyst_estimates",
        "macro_data",
    ],
    "Features, modelos y predicciones": [
        "feature_snapshots",
        "models",
        "model_versions",
        "predictions",
        "live_predictions",
    ],
    "Backtest e investigación": [
        "backtest_runs",
        "backtest_observations",
        "realized_returns",
        "experiments",
        "error_analysis",
        "holdout_access_log",
        "holdout_evaluations",
    ],
}


def main() -> None:
    tables = Base.metadata.tables
    covered = {t for ts in GROUPS.values() for t in ts}
    missing = set(tables) - covered
    assert not missing, f"tables not grouped: {missing}"
    out = [
        "# Modelo de datos",
        "",
        "> Generado por `scripts/gen_data_model_doc.py` desde `pitquant.db.models`. "
        "No editar a mano.",
        "",
        "Convenciones: `*_at` = instante UTC timezone-aware; `*_date` = fecha de calendario; "
        "intervalos semiabiertos `[from, to)`; "
        "🔒 = tabla append-only (guard ORM + trigger PostgreSQL).",
        "",
        f"Tablas: **{len(tables)}**.",
        "",
    ]
    for group, names in GROUPS.items():
        out += [f"## {group}", ""]
        for name in names:
            t = tables[name]
            lock = " 🔒" if name in IMMUTABLE_TABLES else ""
            out += [
                f"### `{name}`{lock}",
                "",
                "| Columna | Tipo | Nulo | Clave |",
                "|---|---|---|---|",
            ]
            for c in t.columns:
                key = "PK" if c.primary_key else ""
                if c.foreign_keys:
                    fk = next(iter(c.foreign_keys)).target_fullname
                    key = (key + " " if key else "") + f"FK→`{fk}`"
                out.append(f"| `{c.name}` | {c.type} | {'sí' if c.nullable else 'no'} | {key} |")
            extras = []
            for cons in t.constraints:
                if isinstance(cons, CheckConstraint):
                    extras.append(f"CHECK `{cons.sqltext}`")
                elif isinstance(cons, UniqueConstraint):
                    extras.append("UNIQUE (" + ", ".join(c.name for c in cons.columns) + ")")
            for ix in t.indexes:
                if isinstance(ix, Index):
                    extras.append(
                        f"INDEX {ix.name} (" + ", ".join(c.name for c in ix.columns) + ")"
                    )
            if extras:
                out += [""] + [f"- {e}" for e in sorted(extras)]
            out.append("")
    Path("docs/DATA_MODEL.md").write_text("\n".join(out), encoding="utf-8")
    print(f"wrote docs/DATA_MODEL.md ({len(tables)} tables)")


if __name__ == "__main__":
    main()
