"""
Unit tests for Level State Machine Engine.
Verifies state transitions, actions (Fade Reversal vs Breakout Runner), and tactical recommendations.
"""
import pytest
from src.quant_engine.state_machine import LevelStateMachine, LevelState


def test_level_state_machine_dormant():
    """Verify that a level far from current price is DORMANT."""
    sm = LevelStateMachine(proximity_threshold_nq=15.0)
    metrics = {
        "regime": "POSITIVE_GAMMA_MEAN_REVERTING",
        "total_net_gex_millions": 50.0,
        "nq_levels": {
            "call_wall": 21000.0,
            "put_wall": 20000.0,
            "atm_synthetic_pivot": 20500.0,
            "pin_risk_magnet": 20500.0,
            "gamma_flip": 20450.0
        },
        "qqq_levels": {
            "call_wall": 512.0,
            "put_wall": 488.0,
            "atm_synthetic_pivot": 500.0,
            "pin_risk_magnet": 500.0,
            "gamma_flip": 498.8
        },
        "air_pockets": []
    }
    
    # Current price = 20500.0 (Call Wall 21000 is 500 pts away -> DORMANT)
    recs = sm.evaluate(current_nq_price=20500.0, metrics=metrics)
    cw_rec = next(r for r in recs if "CALL WALL" in r.level_name)
    assert cw_rec.state == LevelState.DORMANT
    assert cw_rec.action == "MONITORING"


def test_level_state_machine_absorption_defended():
    """Verify that in Positive GEX, touching a wall activates ABSORPTION_DEFENDED (Fade Reversal)."""
    sm = LevelStateMachine(proximity_threshold_nq=15.0)
    metrics = {
        "regime": "POSITIVE_GAMMA_MEAN_REVERTING",
        "total_net_gex_millions": 85.0,
        "nq_levels": {
            "call_wall": 20800.0,
            "put_wall": 20200.0,
            "atm_synthetic_pivot": 20500.0,
            "pin_risk_magnet": 20500.0,
            "gamma_flip": 20400.0
        },
        "qqq_levels": {
            "call_wall": 507.3,
            "put_wall": 492.7,
            "atm_synthetic_pivot": 500.0,
            "pin_risk_magnet": 500.0,
            "gamma_flip": 497.5
        },
        "air_pockets": []
    }
    
    # Current price = 20801.0 (Testing Call Wall 20800 in Positive GEX)
    recs = sm.evaluate(current_nq_price=20801.0, metrics=metrics)
    cw_rec = next(r for r in recs if "CALL WALL" in r.level_name)
    assert cw_rec.state == LevelState.ABSORPTION_DEFENDED
    assert cw_rec.action == "FADE_REVERSAL"
    assert cw_rec.stop_loss_nq > 20800.0


def test_level_state_machine_sliced_vacuum():
    """Verify that in Negative GEX with an Air Pocket behind, breaking wall activates SLICED_VACUUM."""
    sm = LevelStateMachine(proximity_threshold_nq=15.0)
    metrics = {
        "regime": "NEGATIVE_GAMMA_VOLATILE_EXPANSION",
        "total_net_gex_millions": -45.0,
        "nq_levels": {
            "call_wall": 20900.0,
            "put_wall": 20100.0,
            "atm_synthetic_pivot": 20500.0,
            "pin_risk_magnet": 20500.0,
            "gamma_flip": 20750.0
        },
        "qqq_levels": {
            "call_wall": 509.7,
            "put_wall": 490.2,
            "atm_synthetic_pivot": 500.0,
            "pin_risk_magnet": 500.0,
            "gamma_flip": 506.0
        },
        # Air pocket right behind Put Wall 20100
        "air_pockets": [{"strike_nq": 20080.0, "strike_qqq": 489.7, "total_oi": 150.0}]
    }
    
    # Current price = 20099.0 (Broken Put Wall into Air Pocket)
    recs = sm.evaluate(current_nq_price=20099.0, metrics=metrics)
    pw_rec = next(r for r in recs if "PUT WALL" in r.level_name)
    assert pw_rec.state == LevelState.SLICED_VACUUM
    assert pw_rec.action == "BREAKOUT_RUNNER"
    assert "TUYET DOI KHONG BAT DAY" in pw_rec.risk_warning
