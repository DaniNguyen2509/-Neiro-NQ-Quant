"""
Vectorized Greeks & Black-Scholes Engine for Options Pricing & Hedging Exposure.
Calculates Delta, Gamma, Vega, Vanna, and Charm without requiring external heavy packages.
"""
import math
import numpy as np
from typing import Tuple, Union

try:
    from scipy.stats import norm
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


def _norm_cdf(x: np.ndarray) -> np.ndarray:
    """Standard normal cumulative distribution function (CDF)."""
    if SCIPY_AVAILABLE:
        return norm.cdf(x)
    return 0.5 * (1.0 + np.vectorize(math.erf)(x / math.sqrt(2.0)))


def _norm_pdf(x: np.ndarray) -> np.ndarray:
    """Standard normal probability density function (PDF)."""
    if SCIPY_AVAILABLE:
        return norm.pdf(x)
    return np.exp(-0.5 * (x ** 2)) / math.sqrt(2.0 * math.pi)


def vectorized_black_scholes_greeks(
    spot: float,
    strikes: Union[np.ndarray, list],
    t_years: float,
    r: float,
    ivs: Union[np.ndarray, list],
    is_call: bool = True
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate (Price, Delta, Gamma, Vega, Vanna, Charm) simultaneously using vectorized NumPy.
    
    Returns:
        Tuple of (price, delta, gamma, vega, vanna, charm)
    """
    K = np.asarray(strikes, dtype=float)
    sigma = np.clip(np.asarray(ivs, dtype=float), 0.005, 5.0)
    T = max(float(t_years), 1e-5)
    S = float(spot)
    
    sqrt_T = np.sqrt(T)
    denom = sigma * sqrt_T
    
    d1 = (np.log(np.maximum(1e-4, S / K)) + (r + 0.5 * sigma ** 2) * T) / denom
    d2 = d1 - denom
    
    pdf_d1 = _norm_pdf(d1)
    cdf_d1 = _norm_cdf(d1)
    cdf_d2 = _norm_cdf(d2)
    discount = np.exp(-r * T)
    
    # 1. Price & Delta
    if is_call:
        price = S * cdf_d1 - K * discount * cdf_d2
        delta = cdf_d1
    else:
        price = K * discount * _norm_cdf(-d2) - S * _norm_cdf(-d1)
        delta = cdf_d1 - 1.0
        
    # 2. Gamma (Same for Call and Put)
    gamma = pdf_d1 / (S * denom)
    
    # 3. Vega (Same for Call and Put, per 1% change)
    vega = S * pdf_d1 * sqrt_T * 0.01
    
    # 4. Vanna (dDelta / dSigma)
    vanna = - pdf_d1 * (d2 / sigma)
    
    # 5. Charm (- dDelta / dT) (Delta decay per year)
    charm = - pdf_d1 * (r / denom - d2 / (2.0 * T))
    
    return price, delta, gamma, vega, vanna, charm


def estimate_iv_brent(
    price_target: float,
    spot: float,
    strike: float,
    t_years: float,
    r: float,
    is_call: bool = True
) -> float:
    """Estimate Implied Volatility via Bisection search if IV is 0 or missing."""
    if price_target <= 0.01:
        return 0.15
        
    low_iv, high_iv = 0.01, 3.0
    for _ in range(25):
        mid_iv = 0.5 * (low_iv + high_iv)
        p, _, _, _, _, _ = vectorized_black_scholes_greeks(spot, [strike], t_years, r, [mid_iv], is_call=is_call)
        diff = p[0] - price_target
        if abs(diff) < 0.01:
            return float(mid_iv)
        if diff > 0:
            high_iv = mid_iv
        else:
            low_iv = mid_iv
            
    return float(0.5 * (low_iv + high_iv))
