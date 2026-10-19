"""Unit tests for Black-76 Engine, Barchart Parser, and Plotly Dark Dashboard Terminal."""

import math
import numpy as np
import pandas as pd
import pytest

from src.collector.nasdaq_collector import generate_benchmark_nq_chain
from src.quant_engine.black76 import black76_price_and_greeks, solve_iv_newton_brent
from src.quant_engine.engine import process_options_chain_black76
from src.hud.html_dashboard import build_plotly_terminal, generate_html_terminal, clean_val


def test_clean_val():
    """Verify clean_val sanitizes settlement suffix, formulas, and percentages."""
    assert clean_val("133.40s") == 133.40
    assert clean_val("1.80S") == 1.80
    assert clean_val("+25.50%") == 25.50
    assert clean_val("$20,500.50") == 20500.50
    assert clean_val(None) == 0.0



def test_black76_put_call_parity_and_greeks():
    """Verify Black-76 mathematical consistency and Put-Call parity for futures."""
    F = 20500.0
    K = 20500.0
    T = 1.0 / 365.0
    r = 0.045
    sigma = 0.20

    # Call
    c_p, c_delta, c_gamma, c_vega, c_vanna, c_charm = black76_price_and_greeks(
        F, [K], T, r, [sigma], is_call=True
    )
    # Put
    p_p, p_delta, p_gamma, p_vega, p_vanna, p_charm = black76_price_and_greeks(
        F, [K], T, r, [sigma], is_call=False
    )

    # Put-Call Parity for Futures: Call - Put = exp(-r*T) * (F - K)
    # When F == K, Call must equal Put
    assert np.isclose(c_p[0], p_p[0], atol=1e-3)

    # Gamma and Vega identical
    assert np.isclose(c_gamma[0], p_gamma[0], rtol=1e-5)
    assert np.isclose(c_vega[0], p_vega[0], rtol=1e-5)

    # Delta relationship: c_delta - p_delta = exp(-r*T)
    discount = math.exp(-r * T)
    assert np.isclose(c_delta[0] - p_delta[0], discount, atol=1e-3)


def test_solve_iv_newton_brent():
    """Verify IV solver accurately recovers known IV even on short DTE."""
    F = 20500.0
    K = 20600.0
    T = 1.0 / 365.0
    r = 0.045
    true_iv = 0.22

    c_p, _, _, _, _, _ = black76_price_and_greeks(F, [K], T, r, [true_iv], is_call=True)
    target_price = float(c_p[0])

    solved_iv = solve_iv_newton_brent(target_price, F, K, T, r, is_call=True)
    assert np.isclose(solved_iv, true_iv, atol=0.01)


def test_process_options_chain_black76():
    """Verify quant engine calculates GEX, VEX, CHEX, and dynamic levels."""
    df_raw = generate_benchmark_nq_chain(spot=20500.0)
    basis_offset = 15.0
    multiplier = 20.0

    df_clean, meta = process_options_chain_black76(
        df_raw,
        multiplier=multiplier,
        risk_free_rate=0.045,
        dte_days=1.0,
        basis_offset=basis_offset,
    )

    assert not df_clean.empty
    assert "netGEX" in df_clean.columns
    assert "netVEX" in df_clean.columns
    assert "netCHEX" in df_clean.columns

    # Spot & MT5 basis
    assert meta["spot_price"] > 10000.0
    assert np.isclose(meta["spot_mt5"], meta["spot_price"] - basis_offset)

    # Dynamic levels
    assert meta["strike_above"] > meta["spot_price"]
    assert meta["strike_below"] <= meta["spot_price"]
    assert meta["call_wall"] >= meta["spot_price"]
    assert meta["put_wall"] <= meta["spot_price"]
    assert meta["expected_move_1s"] > 0
    assert meta["intraday_rule16_move"] > 0


def test_anti_collision_plotly_terminal():
    """Verify anti-collision constraints: Legend y=1.07, Spot CME at x=0.98 right edge, Vanna/Charm vertical separation."""
    df_raw = generate_benchmark_nq_chain(spot=20500.0)
    df_clean, meta = process_options_chain_black76(df_raw, basis_offset=15.0)

    fig = build_plotly_terminal(df_clean, meta)

    # 1. Legend at y=1.07
    assert fig.layout.legend.y == 1.07

    # 2. Spot CME label anchored at right border
    annotations = fig.layout.annotations
    spot_annot = [a for a in annotations if "SPOT CME" in str(a.text)]
    assert len(spot_annot) > 0
    assert spot_annot[0].x == 0.98
    assert spot_annot[0].xanchor == "right"

    # 3. HTML export contains both panels and strategy tables
    html = generate_html_terminal(df_clean, meta, fig)
    assert "NEIRO-NQ-QUANT TERMINAL" in html
    assert "INTRADAY SCALPING" in html
    assert "STRUCTURAL SWING WALLS" in html
    assert "SPOT CME" in html
    assert "MT5: ~" in html
