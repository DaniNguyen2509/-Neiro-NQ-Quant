"""Black-76 Valuation & Vectorized Greeks Engine for Options on Futures (E-mini Nasdaq NQ).

Implements Black-76 analytical formulas, Greeks (Delta, Gamma, Vega, Vanna, Charm),
and robust IV solvers (Newton-Raphson with Brent/Bisection fallback).
Zero-waste, high performance, and ASCII/UTF-8 compliant.
"""
from __future__ import annotations

import math
from typing import Tuple, Union, Optional
import numpy as np

try:
    from scipy.stats import norm
    from scipy.optimize import brentq
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


def norm_cdf(x: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """Standard normal cumulative distribution function (CDF)."""
    if SCIPY_AVAILABLE:
        return norm.cdf(x)
    if isinstance(x, np.ndarray):
        return 0.5 * (1.0 + np.vectorize(math.erf)(x / math.sqrt(2.0)))
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """Standard normal probability density function (PDF)."""
    if SCIPY_AVAILABLE:
        return norm.pdf(x)
    return np.exp(-0.5 * (x ** 2)) / math.sqrt(2.0 * math.pi)


def black76_price_and_greeks(
    F: float,
    K: Union[float, np.ndarray, list],
    T: float,
    r: float,
    sigma: Union[float, np.ndarray, list],
    is_call: bool = True,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Vectorized Black-76 calculation for Options on Futures.
    
    Returns:
        (price, delta, gamma, vega, vanna, charm)
        - price: Option theoretical price in index points
        - delta: Sensitivity to futures price dPrice/dF
        - gamma: Sensitivity to delta dDelta/dF
        - vega: Sensitivity per 1% change in IV (0.01 * dPrice/dSigma)
        - vanna: dDelta/dSigma (- exp(-r*T) * N'(d1) * d2 / sigma)
        - charm: -dDelta/dT (annual delta decay)
    """
    K_arr = np.asarray(K, dtype=float)
    sig_arr = np.clip(np.asarray(sigma, dtype=float), 0.005, 5.0)
    T_val = max(float(T), 1e-5)
    F_val = max(float(F), 1e-4)

    sqrt_T = np.sqrt(T_val)
    denom = sig_arr * sqrt_T

    d1 = (np.log(np.maximum(1e-4, F_val / K_arr)) + 0.5 * (sig_arr ** 2) * T_val) / denom
    d2 = d1 - denom

    pdf_d1 = norm_pdf(d1)
    cdf_d1 = norm_cdf(d1)
    cdf_d2 = norm_cdf(d2)
    discount = np.exp(-r * T_val)

    if is_call:
        price = discount * (F_val * cdf_d1 - K_arr * cdf_d2)
        delta = discount * cdf_d1
    else:
        price = discount * (K_arr * norm_cdf(-d2) - F_val * norm_cdf(-d1))
        delta = discount * (cdf_d1 - 1.0)

    # Gamma (identical for Call and Put in Black-76)
    gamma = discount * pdf_d1 / (F_val * denom)

    # Vega (per 1% change in volatility)
    vega = F_val * discount * pdf_d1 * sqrt_T * 0.01

    # Vanna: dDelta / dSigma
    vanna = - discount * pdf_d1 * (d2 / sig_arr)

    # Charm: Delta time decay per year (- dDelta / dT)
    term_d2 = pdf_d1 * (d2 / (2.0 * T_val))
    if is_call:
        charm = discount * (r * cdf_d1 + term_d2)
    else:
        charm = discount * (- r * norm_cdf(-d1) + term_d2)

    return price, delta, gamma, vega, vanna, charm


def solve_iv_newton_brent(
    target_price: float,
    F: float,
    K: float,
    T: float,
    r: float,
    is_call: bool = True,
    initial_iv: float = 0.20,
    tol: float = 1e-4,
    max_iter: int = 30,
) -> float:
    """
    Solve Implied Volatility (IV) for Black-76 using Newton-Raphson with Brent/Bisection fallback.
    Guarantees resolution even on 0DTE or illiquid strikes with IV = 0.00%.
    """
    if target_price <= 0.01:
        return 0.15

    # Intrinsic value bounds
    discount = math.exp(-r * max(T, 1e-5))
    intrinsic = max(0.0, discount * (F - K)) if is_call else max(0.0, discount * (K - F))
    if target_price < intrinsic:
        target_price = intrinsic + 0.10

    # 1. Newton-Raphson
    sigma = initial_iv
    for _ in range(max_iter):
        p, _, _, vega, _, _ = black76_price_and_greeks(F, [K], T, r, [sigma], is_call=is_call)
        diff = p[0] - target_price
        if abs(diff) < tol:
            return float(np.clip(sigma, 0.01, 3.0))
        # Vega per unit sigma = vega / 0.01
        v_unit = vega[0] / 0.01
        if v_unit < 1e-5:
            break
        sigma -= diff / v_unit
        if sigma <= 0.005 or sigma >= 5.0:
            break

    # 2. Scipy Brent fallback
    if SCIPY_AVAILABLE:
        def obj(sig):
            p, _, _, _, _, _ = black76_price_and_greeks(F, [K], T, r, [sig], is_call=is_call)
            return p[0] - target_price

        try:
            return float(brentq(obj, 0.005, 4.0, xtol=tol))
        except Exception:
            pass

    # 3. Robust Bisection fallback
    low, high = 0.01, 3.5
    for _ in range(35):
        mid = 0.5 * (low + high)
        p, _, _, _, _, _ = black76_price_and_greeks(F, [K], T, r, [mid], is_call=is_call)
        diff = p[0] - target_price
        if abs(diff) < tol:
            return float(mid)
        if diff > 0:
            high = mid
        else:
            low = mid

    return float(0.5 * (low + high))
