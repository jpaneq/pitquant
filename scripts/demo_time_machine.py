"""Example: point-in-time reconstruction on the SYNTHETIC market (NOT real data).

Run:  python scripts/demo_time_machine.py

Shows, for SYNA on 2020-10-30 after the close, exactly what the platform could know,
when the position could be entered, and when each label becomes knowable.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from pitquant.backtest.labels import label_window
from pitquant.config.settings import load_settings
from pitquant.core.types import Horizon
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.point_in_time.context import PITContext
from pitquant.data.point_in_time.engine import latest_for_period
from pitquant.db.session import create_all, make_engine, make_session_factory
from pitquant.jobs.demo import load_synthetic_market

NY = ZoneInfo("America/New_York")


def main() -> None:
    cfg = load_settings()
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    factory = make_session_factory(engine)
    print("Loading SYNTHETIC market (not real data)…")
    load_synthetic_market(factory, cfg)

    as_of = datetime(2020, 10, 30, 16, 0, tzinfo=NY)
    cal = get_calendar("XNYS")
    with factory() as s:
        ctx = PITContext(s, as_of)
        sec_id = ctx.resolve("SYNA", "XNYS")
        view = ctx.security(sec_id)
        bars = ctx.raw_bars(sec_id)
        adj = ctx.adjusted_closes(sec_id)
        facts = ctx.facts(sec_id, ["revenue"])
        latest_key, latest_fact = max(facts.items(), key=lambda kv: kv[0].period_end)
        universe = ctx.universe("SYN_SP500", "XNYS")

        print(f"\n=== TIME MACHINE — as_of {as_of.isoformat()} — {view.name} [{view.ticker}] ===")
        print(f"synthetic data        : {view.is_synthetic}")
        print(f"universe size (PIT)   : {len(universe)}")
        print(f"last bar used         : {bars.index[-1]}  (raw close {bars['close'].iloc[-1]:.2f})")
        print(
            f"bars available        : {len(bars)}; adjusted (as-of) first close {adj.iloc[0]:.4f}"
        )
        print(
            f"latest revenue known  : {latest_key.period_end} = {latest_fact.value} "
            f"(available {latest_fact.available_at.isoformat()})"
        )
        q3_known = latest_for_period(facts, "revenue", date(2020, 9, 30)) is not None
        print(f"Q3-2020 revenue known?: {q3_known}  (published 2020-11-05 -> must be False)")
        for h in (Horizon.M6, Horizon.M12):
            w = label_window(cal, as_of, h, data_lag_minutes=cfg.pit.label_data_lag_minutes)
            print(
                f"{h.value:>4}: entry {w.t_exec.isoformat()}  label_end {w.label_end.isoformat()}"
                f"  label known {w.label_available_at.isoformat()}"
            )
        print("\nSignal: not produced — scoring engine is Phase 5 (no fabricated output).")


if __name__ == "__main__":
    main()
