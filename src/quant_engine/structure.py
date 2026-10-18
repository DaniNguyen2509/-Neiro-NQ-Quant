"""
Market Microstructure & Structural Levels Engine for E-mini Nasdaq.
Inherits full 3-Tier Quantitative Knowledge Tree & State Machine from Neiro-Quant:
- Tier 1: Microstructure (Mid-Price, Open Interest Distribution)
- Tier 2: Implied Valuation (Synthetic ATM Pivot, Straddle, 1-Sigma & 2-Sigma Bands)
- Tier 3: Dealer Positioning (Call/Put Walls, Pin Risk Magnet, Gamma Squeeze Triggers, Zero Gamma Flip, Air Pockets)
- Level State Machine: DORMANT, TESTING, ABSORPTION_DEFENDED, SLICED_VACUUM
"""
import math
import numpy as np
import pandas as pd
from typing import Dict, Any, List


def calculate_microstructure_levels(
    df: pd.DataFrame,
    spot_price: float,
    basis_ratio: float,
    r: float = 0.045,
    dte_days: float = 1.0,
    air_pocket_threshold: float = 0.35,
    sigma_factor: float = 0.85
) -> Dict[str, Any]:
    """
    Computes complete quantitative tactical matrix for E-mini Nasdaq.
    All levels are provided in both QQQ Strikes and NQ Futures Equivalents.
    """
    if df.empty or len(df) < 3:
        raise ValueError("DataFrame is too small to calculate microstructure levels.")

    # 1. Structural Walls & Pin Risk Magnet (Tier 3)
    call_wall_idx = df['callOpenInterest'].idxmax()
    put_wall_idx = df['putOpenInterest'].idxmax()
    abs_gex_idx = df['netGEX'].abs().idxmax()
    
    call_wall_strike = float(df.loc[call_wall_idx, 'strike'])
    put_wall_strike = float(df.loc[put_wall_idx, 'strike'])
    abs_gex_strike = float(df.loc[abs_gex_idx, 'strike'])
    
    c_mid_cw = float(df.loc[call_wall_idx, 'callMid'])
    p_mid_pw = float(df.loc[put_wall_idx, 'putMid'])
    
    # Gamma Squeeze Triggers
    trigger_up = call_wall_strike + c_mid_cw
    trigger_down = put_wall_strike - p_mid_pw
    
    # Pin Risk Magnet (Top Combined OI Strike)
    df_combined_oi = df['callOpenInterest'] + df['putOpenInterest']
    pin_magnet_idx = df_combined_oi.idxmax()
    pin_magnet_strike = float(df.loc[pin_magnet_idx, 'strike'])

    # 2. ATM Pivot & Straddle (Tier 2)
    atm_idx = (df['callMid'] - df['putMid']).abs().idxmin()
    atm_strike = float(df.loc[atm_idx, 'strike'])
    c_mid_atm = float(df.loc[atm_idx, 'callMid'])
    p_mid_atm = float(df.loc[atm_idx, 'putMid'])
    
    T_years = max(dte_days / 365.0, 1.0 / 365.0)
    implied_pivot = atm_strike + math.exp(r * T_years) * (c_mid_atm - p_mid_atm)
    atm_straddle = max(0.5, c_mid_atm + p_mid_atm)
    
    # 1-Sigma Bands (Standard and Conservative 0.85 0DTE factor)
    upper_band_1s = implied_pivot + atm_straddle
    lower_band_1s = implied_pivot - atm_straddle
    upper_band_085s = implied_pivot + sigma_factor * atm_straddle
    lower_band_085s = implied_pivot - sigma_factor * atm_straddle
    upper_band_2s = implied_pivot + 2.0 * atm_straddle
    lower_band_2s = implied_pivot - 2.0 * atm_straddle
    
    # 3. Total Net GEX & Market Regime
    total_net_gex = float(df['netGEX'].sum())
    if total_net_gex > 0:
        regime = "POSITIVE_GAMMA_MEAN_REVERTING"
        regime_desc = "Dealer hấp thụ biến động (Bán khi tăng, Mua khi giảm). Nén chặt biên độ, ưu tiên Fade Reversal."
    else:
        regime = "NEGATIVE_GAMMA_VOLATILE_EXPANSION"
        regime_desc = "Dealer khuếch đại xu hướng (Mua đuổi khi tăng, Bán tháo khi giảm). Cực kỳ nguy hiểm khi chạm Air Pocket."
        
    # 4. Zero Gamma Flip Point
    flip_strike = None
    sorted_df = df.sort_values('strike').reset_index(drop=True)
    for i in range(len(sorted_df) - 1):
        g1 = sorted_df.loc[i, 'netGEX']
        g2 = sorted_df.loc[i + 1, 'netGEX']
        if g1 * g2 <= 0 and g1 != g2:
            s1 = sorted_df.loc[i, 'strike']
            s2 = sorted_df.loc[i + 1, 'strike']
            flip_strike = float(s1 - g1 * (s2 - s1) / (g2 - g1))
            break
            
    if flip_strike is None:
        flip_strike = abs_gex_strike

    # 5. Liquidity Air Pockets (Vùng chân không thanh khoản OI < 35% mean)
    total_oi = df['callOpenInterest'] + df['putOpenInterest']
    mean_oi = total_oi.mean()
    cutoff_oi = mean_oi * air_pocket_threshold
    
    air_pocket_strikes = []
    for _, r_row in df.iterrows():
        stk = float(r_row['strike'])
        oi = float(r_row['callOpenInterest'] + r_row['putOpenInterest'])
        if oi < cutoff_oi and abs(stk - atm_strike) <= 30:
            air_pocket_strikes.append({
                "strike_qqq": stk,
                "strike_nq": round(stk * basis_ratio, 2),
                "total_oi": oi
            })

    # 6. Real-Time Level State Machine (Neiro Level State Engine)
    nq_current = spot_price * basis_ratio
    cw_nq = call_wall_strike * basis_ratio
    pw_nq = put_wall_strike * basis_ratio
    pivot_nq = implied_pivot * basis_ratio
    
    def evaluate_level_state(level_price: float, is_wall: bool = False) -> str:
        dist = abs(nq_current - level_price)
        if dist > 35.0:
            return "DORMANT"
        elif dist <= 10.0:
            if total_net_gex > 0:
                return "ABSORPTION_DEFENDED"
            else:
                return "SLICING_RISK"
        else:
            return "TRIGGERED_TESTING"

    level_states = {
        "call_wall": evaluate_level_state(cw_nq, is_wall=True),
        "put_wall": evaluate_level_state(pw_nq, is_wall=True),
        "atm_pivot": evaluate_level_state(pivot_nq)
    }

    # Output Full Matrix
    return {
        "spot_price_qqq": round(spot_price, 2),
        "nq_futures_price": round(nq_current, 2),
        "basis_ratio": round(basis_ratio, 4),
        "regime": regime,
        "regime_description": regime_desc,
        "total_net_gex_millions": round(total_net_gex, 2),
        "level_states": level_states,
        "qqq_levels": {
            "call_wall": round(call_wall_strike, 2),
            "put_wall": round(put_wall_strike, 2),
            "pin_risk_magnet": round(pin_magnet_strike, 2),
            "trigger_up": round(trigger_up, 2),
            "trigger_down": round(trigger_down, 2),
            "absolute_gamma_strike": round(abs_gex_strike, 2),
            "atm_synthetic_pivot": round(implied_pivot, 2),
            "gamma_flip": round(flip_strike, 2),
            "straddle_implied_move": round(atm_straddle, 2),
            "upper_band_1s": round(upper_band_1s, 2),
            "lower_band_1s": round(lower_band_1s, 2),
            "upper_band_085s": round(upper_band_085s, 2),
            "lower_band_085s": round(lower_band_085s, 2),
            "upper_band_2s": round(upper_band_2s, 2),
            "lower_band_2s": round(lower_band_2s, 2),
        },
        "nq_levels": {
            "call_wall": round(cw_nq, 2),
            "put_wall": round(pw_nq, 2),
            "pin_risk_magnet": round(pin_magnet_strike * basis_ratio, 2),
            "trigger_up": round(trigger_up * basis_ratio, 2),
            "trigger_down": round(trigger_down * basis_ratio, 2),
            "absolute_gamma_strike": round(abs_gex_strike * basis_ratio, 2),
            "atm_synthetic_pivot": round(pivot_nq, 2),
            "gamma_flip": round(flip_strike * basis_ratio, 2),
            "straddle_implied_move": round(atm_straddle * basis_ratio, 2),
            "upper_band_1s": round(upper_band_1s * basis_ratio, 2),
            "lower_band_1s": round(lower_band_1s * basis_ratio, 2),
            "upper_band_085s": round(upper_band_085s * basis_ratio, 2),
            "lower_band_085s": round(lower_band_085s * basis_ratio, 2),
            "upper_band_2s": round(upper_band_2s * basis_ratio, 2),
            "lower_band_2s": round(lower_band_2s * basis_ratio, 2),
        },
        "air_pockets": air_pocket_strikes
    }
