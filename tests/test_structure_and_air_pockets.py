"""Unit tests for Liquidity Air Pocket detection and polymorphic extraction."""

import numpy as np
import pandas as pd
import pytest

from src.quant_engine.structure import detect_strike_air_pockets, AirPocketZone
from src.quant_engine.state_machine import LevelStateMachine, LevelState


def test_detect_strike_air_pockets_empty():
    """Verify empty or small DataFrame returns empty list."""
    assert detect_strike_air_pockets(pd.DataFrame(), 20000.0, 20500.0) == []
    df_small = pd.DataFrame({"strike": [20000.0], "callOpenInterest": [100], "putOpenInterest": [100]})
    assert detect_strike_air_pockets(df_small, 20000.0, 20500.0) == []


def test_detect_strike_air_pockets_valid():
    """Verify contiguous low-OI strikes form AirPocketZone."""
    # Strikes from 20000 to 20500 with step 50
    strikes = [20000.0, 20050.0, 20100.0, 20150.0, 20200.0, 20250.0, 20300.0, 20350.0, 20400.0, 20450.0, 20500.0]
    # Mean total OI ~ 1000. Low OI pocket at 20150, 20200 (OI = 50 each, << 400 cutoff)
    call_oi = [500, 500, 600, 25, 25, 600, 500, 500, 500, 500, 500]
    put_oi  = [500, 500, 400, 25, 25, 400, 500, 500, 500, 500, 500]
    vol     = [100] * len(strikes)

    df = pd.DataFrame({
        "strike": strikes,
        "callOpenInterest": call_oi,
        "putOpenInterest": put_oi,
        "callVolume": vol,
        "putVolume": vol,
    })

    pockets = detect_strike_air_pockets(df, start_strike=20000.0, end_strike=20500.0, threshold_ratio=0.40)
    assert len(pockets) >= 1
    p = pockets[0]
    assert isinstance(p, AirPocketZone)
    assert p.start_strike == 20150.0
    assert p.end_strike == 20250.0
    assert p.gap_size == 100.0
    assert p.avg_oi == 50.0
    assert p.direction == "UP"


def test_state_machine_polymorphic_air_pockets():
    """Verify LevelStateMachine handles both dicts and AirPocketZone objects without KeyError."""
    sm = LevelStateMachine()
    metrics = {
        "regime": "NEGATIVE_GAMMA_VOLATILE_EXPANSION",
        "total_net_gex_millions": -50.0,
        "nq_levels": {
            "call_wall": 20800.0,
            "put_wall": 20200.0,
            "atm_synthetic_pivot": 20500.0,
            "gamma_flip": 20400.0,
        },
        "qqq_levels": {
            "call_wall": 500.0,
            "put_wall": 485.0,
            "atm_synthetic_pivot": 492.0,
            "gamma_flip": 490.0,
        },
        "air_pockets": [
            {"from": 20180.0, "to": 20220.0, "severity": "HIGH"},
            AirPocketZone(start_strike=20780.0, end_strike=20820.0, gap_size=40.0, avg_oi=10.0, avg_volume=5.0),
        ],
    }

    # Evaluate when price is right at put wall (20200) where air pocket is behind
    recs = sm.evaluate(current_nq_price=20200.0, metrics=metrics)
    assert len(recs) > 0
    put_wall_rec = next(r for r in recs if "PUT WALL" in r.level_name)
    assert put_wall_rec.state == LevelState.SLICED_VACUUM

