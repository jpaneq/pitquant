"""Property-based anti-leakage tests (§81). Invariants must hold for ANY input."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest
from dateutil.relativedelta import relativedelta
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pitquant.core.errors import LookAheadError
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.point_in_time.engine import PITRecord, as_of_view
from pitquant.features.snapshot import FeatureValue, SnapshotBuilder
from pitquant.validation.splits import PurgedWalkForward

pytestmark = pytest.mark.pit

instants = st.datetimes(
    min_value=datetime(2000, 1, 1), max_value=datetime(2025, 12, 31), timezones=st.just(UTC)
)


@given(
    records=st.lists(
        st.tuples(
            st.sampled_from(["a", "b"]),
            st.sampled_from([date(2020, 3, 31), date(2020, 6, 30)]),
            instants,
            st.integers(0, 3),
            st.floats(-1e6, 1e6, allow_nan=False),
        ),
        max_size=40,
    ),
    as_of=instants,
)
def test_as_of_view_never_returns_future_and_returns_latest(records, as_of) -> None:  # type: ignore[no-untyped-def]
    recs = [PITRecord(k, pe, av, v, rev) for k, pe, av, rev, v in records]
    view = as_of_view(recs, as_of)
    for (key, pe), r in view.items():
        assert r.available_at <= as_of
        candidates = [
            x for x in recs if x.key == key and x.period_end == pe and x.available_at <= as_of
        ]
        assert (r.available_at, r.revision_id) == max(
            (x.available_at, x.revision_id) for x in candidates
        )
    # every key with at least one known record is present
    known = {(x.key, x.period_end) for x in recs if x.available_at <= as_of}
    assert set(view) == known


@given(as_of=instants, offsets=st.lists(st.integers(-(10**7), 10**7), min_size=1, max_size=15))
def test_snapshot_max_available_at_le_as_of_or_fails(as_of, offsets) -> None:  # type: ignore[no-untyped-def]
    b = SnapshotBuilder("s", as_of, "f", "d", "c")
    for i, off in enumerate(offsets):
        b.add(FeatureValue(f"f{i}", 1.0, as_of + timedelta(seconds=off)))
    if max(offsets) > 0:
        with pytest.raises(LookAheadError):
            b.freeze()
    else:
        snap = b.freeze()
        assert snap.max_available_at is not None and snap.max_available_at <= snap.as_of


@settings(max_examples=60, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    ts=st.datetimes(
        min_value=datetime(2001, 1, 1), max_value=datetime(2026, 6, 30), timezones=st.just(UTC)
    ),
    code=st.sampled_from(["XNYS", "XMAD"]),
)
def test_next_session_open_strictly_after_and_is_a_real_open(ts, code) -> None:  # type: ignore[no-untyped-def]
    cal = get_calendar(code)
    nxt = cal.next_session_open(ts)
    assert nxt > ts
    session = pd.Timestamp(nxt).tz_convert(cal.tz).date()
    assert cal.is_session(session) and cal.session_open(session) == nxt
    assert cal.session_close(cal.last_closed_session(ts)) <= ts


@settings(max_examples=25, deadline=None)
@given(
    h=st.sampled_from([1, 3, 6, 12]),
    emb=st.integers(0, 12),
    val=st.integers(0, 24),
    test_m=st.sampled_from([6, 12]),
    lag_h=st.integers(0, 72),
)
def test_every_fold_respects_label_availability_and_purging(h, emb, val, test_m, lag_h) -> None:  # type: ignore[no-untyped-def]
    t = pd.date_range("2000-01-01", "2020-12-01", freq="MS", tz="UTC")
    le = pd.DatetimeIndex([x + pd.DateOffset(months=h) for x in t])
    obs = pd.DataFrame(
        {"t_exec": t, "label_end": le, "label_available_at": le + pd.Timedelta(hours=lag_h)}
    )
    wf = PurgedWalkForward(
        first_test_start=date(2008, 1, 1),
        validation_months=val,
        test_months=test_m,
        step_months=12,
        embargo=relativedelta(months=emb),
    )
    for f in wf.split(obs, last_test_end=date(2021, 1, 1)):
        tr, va = obs.loc[f.train_idx], obs.loc[f.val_idx]
        assert (tr["label_available_at"] <= f.train_cutoff).all()
        assert (va["label_available_at"] <= f.decision_time).all()
        assert set(f.train_idx).isdisjoint(set(f.test_idx) | set(f.val_idx))
        if len(tr) and len(f.test_idx):
            assert tr["label_end"].max() <= obs.loc[f.test_idx, "t_exec"].min()
