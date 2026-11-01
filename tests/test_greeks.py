"""
Unit tests for Vectorized Greeks and Black-Scholes Engine.
Tests Delta, Gamma, Vega, Vanna, Charm, and Implied Volatility Solver.
"""
import pytest
import numpy as np
from src.collector.greeks import vectorized_black_scholes_greeks, estimate_iv_brent


def test_black_scholes_at_the_money():
    """Verify that ATM call and put options produce mathematically consistent Greeks."""
    spot = 500.0
    strikes = [500.0]
    t_years = 30.0 / 365.0
    r = 0.05
    ivs = [0.20]
    
    # Calls (6 values: price, delta, gamma, vega, vanna, charm)
    c_price, c_delta, c_gamma, c_vega, c_vanna, c_charm = vectorized_black_scholes_greeks(
        spot, strikes, t_years, r, ivs, is_call=True
    )
    # Puts
    p_price, p_delta, p_gamma, p_vega, p_vanna, p_charm = vectorized_black_scholes_greeks(
        spot, strikes, t_years, r, ivs, is_call=False
    )
    
    # 1. Delta: Call Delta ~ 0.5, Put Delta ~ -0.5, and Call Delta - Put Delta = 1.0 (approx)
    assert 0.45 < c_delta[0] < 0.60
    assert -0.55 < p_delta[0] < -0.40
    assert np.isclose(c_delta[0] - p_delta[0], 1.0, atol=0.05)
    
    # 2. Gamma must be positive and identical for Call and Put
    assert c_gamma[0] > 0
    assert np.isclose(c_gamma[0], p_gamma[0])
    
    # 3. Vega must be positive and identical for Call and Put
    assert c_vega[0] > 0
    assert np.isclose(c_vega[0], p_vega[0])

    # 4. Vanna should be identical for Call and Put
    assert np.isclose(c_vanna[0], p_vanna[0])

    # 5. Charm mathematically matches numerical derivative -dDelta/dT
    assert np.isfinite(c_charm[0])
    assert np.isfinite(p_charm[0])
    eps = 1e-6
    _, d_plus, _, _, _, _ = vectorized_black_scholes_greeks(spot, strikes, t_years + eps, r, ivs, is_call=True)
    _, d_minus, _, _, _, _ = vectorized_black_scholes_greeks(spot, strikes, t_years - eps, r, ivs, is_call=True)
    num_charm_call = - (d_plus[0] - d_minus[0]) / (2 * eps)
    assert np.isclose(c_charm[0], num_charm_call, atol=1e-4)


def test_vectorization_multiple_strikes():
    """Verify vectorized handling of multiple strikes."""
    spot = 500.0
    strikes = np.array([480.0, 490.0, 500.0, 510.0, 520.0])
    t_years = 1.0 / 365.0
    r = 0.045
    ivs = np.array([0.22, 0.20, 0.18, 0.19, 0.21])
    
    c_price, c_delta, c_gamma, c_vega, c_vanna, c_charm = vectorized_black_scholes_greeks(
        spot, strikes, t_years, r, ivs, is_call=True
    )
    
    assert len(c_price) == 5
    assert len(c_delta) == 5
    assert len(c_charm) == 5
    # In-the-money delta (480) > Out-of-the-money delta (520)
    assert c_delta[0] > c_delta[-1]


def test_estimate_iv_brent():
    """Verify that estimate_iv_brent recovers realistic IV from a known price."""
    spot = 500.0
    strike = 500.0
    t_years = 10.0 / 365.0
    r = 0.045
    known_iv = 0.25
    
    p, _, _, _, _, _ = vectorized_black_scholes_greeks(spot, [strike], t_years, r, [known_iv], is_call=True)
    target_price = float(p[0])
    
    recovered_iv = estimate_iv_brent(target_price, spot, strike, t_years, r, is_call=True)
    assert np.isclose(recovered_iv, known_iv, atol=0.02)
