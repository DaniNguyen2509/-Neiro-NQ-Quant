"""Neiro-NQ-Quant Core Quantitative Engine (Black-76 for Futures Options).

Computes:
- Put-Call Parity Implied Synthetic Futures Pivot
- Vectorized Black-76 Greeks & GEX, VEX, CHEX ($M Exposure)
- 1-Sigma Expected Move (Brenner-Subrahmanyam: Straddle / 0.7979)
- Intraday Expected Move (Rule of 16)
- Dynamic Walls & Tactical Levels (Call/Put Walls, Triggers, ATM Sàn Đỡ, Trạm Nghỉ nấc 2)
Zero-touch automation & ASCII/UTF-8 compliant.
"""
from __future__ import annotations

import math
from typing import Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd

from .black76 import black76_price_and_greeks, solve_iv_newton_brent

BRENNER_SUBRAHMANYAM_CONST = 0.7979
DEFAULT_MULTIPLIER_NQ = 20.0  # 20 USD per point for E-mini NQ futures options


def process_options_chain_black76(
    df: pd.DataFrame,
    multiplier: float = DEFAULT_MULTIPLIER_NQ,
    risk_free_rate: float = 0.045,
    dte_days: float = 1.0,
    basis_offset: float = 0.0,
    underlying_price: Optional[float] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Compute full quantitative matrix for E-mini Nasdaq options chain using Black-76.

    Args:
        df: Input DataFrame with standard columns
        multiplier: Contract multiplier (20 for NQ, 2 for MNQ)
        risk_free_rate: Annualized risk-free interest rate (e.g. 0.045)
        dte_days: Days to expiration (minimum 1/1440 of a day)
        basis_offset: MT5 Spot Basis Offset (Spot_MT5 = Spot_Futures - basis_offset)

    Returns:
        (Enriched DataFrame, Quantitative Metadata Dictionary)
    """
    if df.empty or len(df) < 3:
        raise ValueError("DataFrame is too small to calculate quantitative metrics.")

    df_clean = df.copy().sort_values("strike").reset_index(drop=True)

    # Standardize and sanitize prices
    for col in ["callMid", "callBid", "callAsk", "callLatest", "callVolume", "callOpenInterest", "callGamma", "callIV",
                "putMid", "putBid", "putAsk", "putLatest", "putVolume", "putOpenInterest", "putGamma", "putIV"]:
        if col not in df_clean.columns:
            df_clean[col] = 0.0
        df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce").fillna(0.0)

    # Fallback mid prices if zero
    mask_c = (df_clean["callMid"] <= 0) & (df_clean["callBid"] > 0) & (df_clean["callAsk"] > 0)
    df_clean.loc[mask_c, "callMid"] = (df_clean.loc[mask_c, "callBid"] + df_clean.loc[mask_c, "callAsk"]) / 2.0
    mask_p = (df_clean["putMid"] <= 0) & (df_clean["putBid"] > 0) & (df_clean["putAsk"] > 0)
    df_clean.loc[mask_p, "putMid"] = (df_clean.loc[mask_p, "putBid"] + df_clean.loc[mask_p, "putAsk"]) / 2.0

    T_years = max(float(dte_days) / 365.0, 1.0 / (365.0 * 1440.0))  # at least 1 minute
    r = float(risk_free_rate)

    # 1. Put-Call Parity Implied Synthetic Futures Pivot
    # Select strike closest to ATM where both Call and Put have real positive quotes
    valid_quotes = df_clean[(df_clean["callMid"] > 0.5) & (df_clean["putMid"] > 0.5)]
    if not valid_quotes.empty:
        diff = (valid_quotes["callMid"] - valid_quotes["putMid"]).abs()
        atm_idx = diff.idxmin()
    else:
        diff = (df_clean["callMid"] - df_clean["putMid"]).abs()
        atm_idx = diff.idxmin()

    atm_strike = float(df_clean.loc[atm_idx, "strike"])
    c_mid_atm = float(df_clean.loc[atm_idx, "callMid"])
    p_mid_atm = float(df_clean.loc[atm_idx, "putMid"])

    # Futures Put-Call Parity: S_implied = K_ATM + exp(r*T) * (Call_ATM - Put_ATM)
    discount = math.exp(-r * T_years)
    s_implied = atm_strike + math.exp(r * T_years) * (c_mid_atm - p_mid_atm)
    if s_implied <= 0 or math.isnan(s_implied):
        s_implied = atm_strike
    real_spot = float(underlying_price) if (underlying_price is not None and underlying_price > 0) else s_implied

    # 2. Implied Volatility Solver (Fix IV = 0.00% on 0DTE or illiquid strikes)
    strikes = df_clean["strike"].values.astype(float)
    call_mids = df_clean["callMid"].values.astype(float)
    put_mids = df_clean["putMid"].values.astype(float)
    c_ivs = df_clean["callIV"].values.astype(float).copy()
    p_ivs = df_clean["putIV"].values.astype(float).copy()

    # Fill zero or artifact IVs via Newton-Brent Black-76 solver
    for i in range(len(df_clean)):
        if c_ivs[i] <= 0.01 or c_ivs[i] >= 2.5 or math.isnan(c_ivs[i]):
            if call_mids[i] > 0.01:
                c_ivs[i] = solve_iv_newton_brent(call_mids[i], s_implied, strikes[i], T_years, r, is_call=True)
            else:
                c_ivs[i] = 0.18
        if p_ivs[i] <= 0.01 or p_ivs[i] >= 2.5 or math.isnan(p_ivs[i]):
            if put_mids[i] > 0.01:
                p_ivs[i] = solve_iv_newton_brent(put_mids[i], s_implied, strikes[i], T_years, r, is_call=False)
            else:
                p_ivs[i] = 0.18

    df_clean["callIV"] = np.round(c_ivs, 4)
    df_clean["putIV"] = np.round(p_ivs, 4)

    # 3. Vectorized Black-76 Greeks
    _, c_delta, c_gamma, c_vega, c_vanna, c_charm = black76_price_and_greeks(
        s_implied, strikes, T_years, r, c_ivs, is_call=True
    )
    _, p_delta, p_gamma, p_vega, p_vanna, p_charm = black76_price_and_greeks(
        s_implied, strikes, T_years, r, p_ivs, is_call=False
    )

    df_clean["callDelta"] = c_delta
    df_clean["callGamma"] = c_gamma
    df_clean["callVega"] = c_vega
    df_clean["callVanna"] = c_vanna
    df_clean["callCharm"] = c_charm

    df_clean["putDelta"] = p_delta
    df_clean["putGamma"] = p_gamma
    df_clean["putVega"] = p_vega
    df_clean["putVanna"] = p_vanna
    df_clean["putCharm"] = p_charm

    # 4. GEX, VEX, CHEX ($M Exposure)
    # GEX: $M per 1% move in futures price
    scale_gex = (real_spot ** 2) * 0.01 / 1e6
    df_clean["callGEX"] = df_clean["callGamma"] * df_clean["callOpenInterest"] * multiplier * scale_gex
    df_clean["putGEX"] = - (df_clean["putGamma"] * df_clean["putOpenInterest"] * multiplier * scale_gex)
    df_clean["netGEX"] = df_clean["callGEX"] + df_clean["putGEX"]

    # VEX: $M per 1% change in IV (Vanna Exposure)
    scale_vex = real_spot * 0.01 / 1e6
    df_clean["callVEX"] = df_clean["callVanna"] * df_clean["callOpenInterest"] * multiplier * scale_vex
    df_clean["putVEX"] = - (df_clean["putVanna"] * df_clean["putOpenInterest"] * multiplier * scale_vex)
    df_clean["netVEX"] = df_clean["callVEX"] + df_clean["putVEX"]

    # CHEX: $M per day of calendar time decay (Charm Exposure)
    scale_chex = real_spot / 1e6
    df_clean["callCHEX"] = (df_clean["callCharm"] / 365.0) * df_clean["callOpenInterest"] * multiplier * scale_chex
    df_clean["putCHEX"] = - ((df_clean["putCharm"] / 365.0) * df_clean["putOpenInterest"] * multiplier * scale_chex)
    df_clean["netCHEX"] = df_clean["callCHEX"] + df_clean["putCHEX"]

    # 5. Volatility & Expected Move Calculations
    atm_straddle = max(1.0, c_mid_atm + p_mid_atm)
    # Brenner-Subrahmanyam 1-Sigma Expected Move
    expected_move_1s = atm_straddle / BRENNER_SUBRAHMANYAM_CONST
    sigma_atm = float(np.clip(atm_straddle / (BRENNER_SUBRAHMANYAM_CONST * real_spot * math.sqrt(T_years)), 0.01, 3.0))
    # Rule of 16 daily move
    intraday_rule16_move = (sigma_atm / 16.0) * real_spot

    upper_band_1s = real_spot + expected_move_1s
    lower_band_1s = real_spot - expected_move_1s
    upper_band_2s = real_spot + 2.0 * expected_move_1s
    lower_band_2s = real_spot - 2.0 * expected_move_1s

    # 6. Structural Walls & Market Regime
    call_wall_row = df_clean.loc[df_clean["callOpenInterest"].idxmax()]
    put_wall_row = df_clean.loc[df_clean["putOpenInterest"].idxmax()]
    call_wall = float(call_wall_row["strike"])
    call_wall_oi = int(call_wall_row["callOpenInterest"])
    put_wall = float(put_wall_row["strike"])
    put_wall_oi = int(put_wall_row["putOpenInterest"])

    # Pin Risk Magnet (Top Combined OI Strike)
    combined_oi = df_clean["callOpenInterest"] + df_clean["putOpenInterest"]
    pin_magnet = float(df_clean.loc[combined_oi.idxmax(), "strike"])

    total_net_gex = float(df_clean["netGEX"].sum())
    total_net_vex = float(df_clean["netVEX"].sum())
    total_net_chex = float(df_clean["netCHEX"].sum())

    if total_net_gex > 5.0:
        regime = "POSITIVE_GAMMA_MEAN_REVERTING"
        regime_desc = "Dealer hấp thụ biến động (Bán khi tăng, Mua khi giảm). Nén chặt biên độ, ưu tiên Fade Reversal."
    elif total_net_gex < -5.0:
        regime = "NEGATIVE_GAMMA_VOLATILE_EXPANSION"
        regime_desc = "Dealer khuếch đại xu hướng (Mua đuổi khi tăng, Bán tháo khi giảm). Cực kỳ nguy hiểm khi thủng cản."
    else:
        regime = "NEUTRAL_GAMMA_TRANSITION"
        regime_desc = "Thị trường chuyển giao trạng thái cân bằng. Cần theo dõi chặt chẽ phản ứng tại trục ATM Pivot."

    # Dynamic step and buffer
    diff_strikes = np.diff(strikes)
    step = float(diff_strikes.min()) if len(diff_strikes) > 0 else 50.0
    buffer_val = min(step * 0.15, 25.0)  # Dynamic buffer (no hardcoding)

    squeeze_trigger = call_wall + buffer_val
    waterfall_trigger = put_wall - buffer_val

    # Dynamic tactical strikes (Decoded strictly dynamically)
    strikes_above = strikes[strikes > real_spot]
    strike_above = float(strikes_above[0]) if len(strikes_above) > 0 else call_wall
    next_above = float(strikes_above[1]) if len(strikes_above) > 1 else strike_above + step

    strikes_below = strikes[strikes <= real_spot]
    strike_below = float(strikes_below[-1]) if len(strikes_below) > 0 else put_wall
    next_below = float(strikes_below[-2]) if len(strikes_below) > 1 else strike_below - step
    secondary_support = next_below

    # MT5 Spot price projection
    spot_mt5 = real_spot - basis_offset

    meta = {
        "spot_price": round(real_spot, 2),
        "s_implied": round(s_implied, 2),
        "spot_mt5": round(spot_mt5, 2),
        "basis_offset": round(basis_offset, 2),
        "multiplier": multiplier,
        "atm_strike": round(atm_strike, 2),
        "atm_straddle": round(atm_straddle, 2),
        "sigma_atm": round(sigma_atm, 4),
        "expected_move_1s": round(expected_move_1s, 2),
        "intraday_rule16_move": round(intraday_rule16_move, 2),
        "upper_band_1s": round(upper_band_1s, 2),
        "lower_band_1s": round(lower_band_1s, 2),
        "upper_band_2s": round(upper_band_2s, 2),
        "lower_band_2s": round(lower_band_2s, 2),
        "call_wall": round(call_wall, 2),
        "call_wall_oi": call_wall_oi,
        "put_wall": round(put_wall, 2),
        "put_wall_oi": put_wall_oi,
        "pin_risk_magnet": round(pin_magnet, 2),
        "total_net_gex": round(total_net_gex, 2),
        "total_net_vex": round(total_net_vex, 2),
        "total_net_chex": round(total_net_chex, 2),
        "regime": regime,
        "regime_description": regime_desc,
        "step": step,
        "buffer_val": round(buffer_val, 2),
        "squeeze_trigger": round(squeeze_trigger, 2),
        "waterfall_trigger": round(waterfall_trigger, 2),
        "strike_above": round(strike_above, 2),
        "next_above": round(next_above, 2),
        "strike_below": round(strike_below, 2),
        "next_below": round(next_below, 2),
        "secondary_support": round(secondary_support, 2),
    }

    return df_clean, meta
