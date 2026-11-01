"""Neiro-NQ-Quant Tactical HTML Dashboard & True ATAS Orderflow Terminal Generator.

Generates a standalone, production-grade ATAS Orderflow Footprint & Quant Terminal for
E-mini Nasdaq-100 Futures Options (NQ / NQZ26 / NAS100) incorporating:
- Live Ticker Realtime Bar (CME Globex NQ=F, SOFR/Treasury 13W ^IRX rate, ATM IV)
- Interactive ATAS Orderflow Footprint Terminal:
  * High-contrast Pure Black ATAS styling (#000000)
  * Brownian-bridge 1-Minute Candlestick generator (zero artificial spike artifacts)
  * HTML5 Canvas Orderflow Layer synchronized with TradingView Lightweight Charts v4.2
  * Horizontal Shaded Execution Stack Zones across the chart:
    - [deep ef stack] (Institutional Execution Flow)
    - [seller offer] (+1R Supply Zone)
    - [gex 5 reaction] (Pivot Reaction Line)
    - [F0 LIVE] (Tick-by-tick Horizontal Price Line)
    - [buyer abs] (Buyer Absorption Zone)
    - [put wall] & [call wall] (Major Gamma Support & Resistance)
  * TrueVision / ATAS Cluster Imbalance Bubbles on Candlesticks
  * Left Volume Profile Histogram (Bid/Ask cluster profile)
- In-Browser Client-Side Black-76 Engine (Pure JS):
  * Recalculates Delta, Gamma, Theta, Vega, Vanna, Charm, and Net GEX ($M) every second
  * Realistic institutional Greek scaling (Theta -$k/day, Vega $M, Vanna, Charm)
  * Updates KPI Cards, Greeks Radar, and ATM Microstructure table tick-by-tick
- Live Tick Feeder / Simulator with interactive user price override slider
- 3-Panel Plotly Interactive Charts & Anti-collision algorithm
- Intraday Scalping Strategy Table (30-50 pts NQ)
- Structural Swing Walls Strategy Table (100-250 pts NQ)
- Bottom Vietnamese Glossary & Tactical Playbook (Giải nghĩa dải cản ATAS)
- Zero-waste & ASCII/UTF-8 compliant.
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.quant_engine.engine import process_options_chain_black76
from src.collector.nasdaq_collector import generate_benchmark_nq_chain


def clean_val(v: Any, default: float = 0.0) -> float:
    """Sanitize dirty string or numeric values cleanly."""
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return default if (math.isnan(v) or math.isinf(v)) else float(v)
    s = str(v).strip().replace('"', '').replace("'", "").replace("$", "")
    for ch in ("=", "+"):
        if s.startswith(ch):
            s = s[1:].strip()
    if s.endswith(("%", "s", "S")):
        s = s[:-1].strip()
    s = s.replace(",", "").replace(" ", "")
    try:
        res = float(s)
        return default if (math.isnan(res) or math.isinf(res)) else res
    except Exception:
        return default


def load_options_dataset(
    csv_path: Optional[str] = None,
    basis: float = 0.0,
    multiplier: float = 20.0,
    source: str = "yfinance",
    spot_override: Optional[float] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Load options dataset from live yfinance (QQQ -> NQ, fast & free, default)
    or fall back to CSV file / embedded benchmark data.
    """
    df_raw = None
    eff_multiplier = multiplier
    eff_basis = basis
    market_fut = spot_override
    fetched_r_rate = 0.0397  # Fallback Treasury 13-Week Bill yield

    # 1. Primary Source: Live yfinance (Fast, 100% Free, No Browser, Bypasses Cloudflare)
    if source == "yfinance":
        try:
            print("[Dashboard] Fetching real-time QQQ options chain via yfinance...")
            from src.collector.nasdaq_collector import NasdaqCollector
            collector = NasdaqCollector()
            df_live, prices = collector.fetch_standardized_nq_chain()
            if market_fut is None and prices and "futures" in prices:
                market_fut = float(prices["futures"])
            if prices and "r_rate" in prices:
                fetched_r_rate = float(prices["r_rate"])
            if not df_live.empty and len(df_live) >= 5:
                df_raw = df_live
                basis_ratio = max(1.0, float(prices.get("basis", 41.3)))
                eff_multiplier = round(100.0 / basis_ratio, 4)

                if eff_basis is None:
                    eff_basis = 0.0

                print(f"[+] Loaded {len(df_raw)} strikes via yfinance (QQQ ${prices['underlying']:.2f} -> NQ {prices['futures']:.2f}, Basis: {basis_ratio:.2f}, EffMult: {eff_multiplier}, r: {fetched_r_rate*100:.2f}%).")
                if csv_path:
                    try:
                        p_csv = Path(csv_path)
                        p_csv.parent.mkdir(parents=True, exist_ok=True)
                        df_raw.to_csv(p_csv, index=False)
                        print(f"[+] Fresh options snapshot saved to CSV: {csv_path}")
                    except Exception as e:
                        print(f"[!] Warning: Could not save snapshot to {csv_path}: {e}")
        except Exception as e:
            print(f"[Dashboard] Notice: yfinance fetch encountered ({e}). Checking CSV/benchmark fallback...")

    # 2. Secondary Source: Local CSV dataset (with quality & freshness validation)
    if (df_raw is None or df_raw.empty) and csv_path and os.path.exists(csv_path):
        try:
            df_cand = pd.read_csv(csv_path)
            col_clean = {c: c.strip() for c in df_cand.columns}
            df_cand.rename(columns=col_clean, inplace=True)
            
            total_oi = 0
            if "callOpenInterest" in df_cand.columns and "putOpenInterest" in df_cand.columns:
                total_oi = float(pd.to_numeric(df_cand["callOpenInterest"], errors="coerce").fillna(0).sum() +
                                 pd.to_numeric(df_cand["putOpenInterest"], errors="coerce").fillna(0).sum())
            
            if total_oi <= 0:
                print(f"[Dashboard] Warning: CSV at {csv_path} has ZERO total Open Interest. Rejecting stale/empty CSV.")
            else:
                df_raw = df_cand
                eff_multiplier = multiplier
                print(f"[+] Loaded {len(df_raw)} strikes from CSV: {csv_path} (Total OI: {int(total_oi):,})")
        except Exception as e:
            print(f"[Dashboard] Warning: Could not read CSV at {csv_path} ({e}). Using benchmark.")
            df_raw = None

    # 3. Tertiary Fallback: High-fidelity benchmark data
    if df_raw is None or df_raw.empty or len(df_raw) < 5:
        print("[Dashboard] Loading high-fidelity E-mini NQ benchmark options chain...")
        df_raw = generate_benchmark_nq_chain(spot=28500.0)
        eff_multiplier = multiplier

    dte_val = 1.0
    if "expirationDate" in df_raw.columns and not df_raw["expirationDate"].empty:
        exp_val = str(df_raw["expirationDate"].iloc[0])
        try:
            from src.collector.nasdaq_collector import calculate_dte
            dte_val = calculate_dte(exp_val)
        except Exception:
            dte_val = 1.0

    df_enriched, meta = process_options_chain_black76(
        df_raw,
        multiplier=eff_multiplier,
        risk_free_rate=fetched_r_rate,
        dte_days=dte_val,
        basis_offset=eff_basis,
        underlying_price=market_fut,
    )
    meta["raw_source"] = source
    meta["effective_multiplier"] = eff_multiplier
    meta["dte_days"] = dte_val
    meta["basis_offset"] = eff_basis
    meta["risk_free_rate"] = fetched_r_rate
    return df_enriched, meta


def build_plotly_terminal(df_full: pd.DataFrame, meta: Dict[str, Any]) -> go.Figure:
    """Build 3-Panel ATAS-style dark terminal figure with anti-collision algorithm."""
    spot_price = meta["spot_price"]
    spot_mt5 = meta["spot_mt5"]
    atm_strike = meta["atm_strike"]
    call_wall = meta["call_wall"]
    call_wall_oi = meta["call_wall_oi"]
    put_wall = meta["put_wall"]
    put_wall_oi = meta["put_wall_oi"]
    step = meta["step"]
    buffer_val = meta["buffer_val"]
    strike_above = meta["strike_above"]
    next_above = meta["next_above"]
    strike_below = meta["strike_below"]
    next_below = meta["next_below"]
    secondary_support = meta["secondary_support"]

    atm_idx = (df_full["strike"] - atm_strike).abs().idxmin()
    window = 20
    half = window // 2
    s_idx = max(0, atm_idx - half)
    e_idx = min(len(df_full), atm_idx + half + 1)
    df = df_full.iloc[s_idx:e_idx].copy().reset_index(drop=True)

    strikes = df["strike"].values

    fig = make_subplots(
        rows=1, cols=3,
        shared_yaxes=True,
        horizontal_spacing=0.035,
        subplot_titles=(
            "<b>Panel 1: Net GEX ($M) & Mốc Chiến Thuật</b>",
            "<b>Panel 2: Dòng Tiền Volume vs Open Interest Nén</b>",
            "<b>Panel 3: Greeks Bậc 2 (Vanna & Charm)</b>",
        ),
        column_widths=[0.36, 0.36, 0.28],
    )

    colors_g = ["#4ADE80" if x >= 0 else "#F87171" for x in df["netGEX"]]
    fig.add_trace(
        go.Bar(
            y=df["strike"], x=df["netGEX"], orientation="h",
            marker_color=colors_g, name="Net GEX ($M)",
            hovertemplate="Strike: %{y:,.0f} pts<br>Net GEX: $%{x:+.2f}M<extra></extra>",
        ),
        row=1, col=1,
    )
    fig.add_vline(x=0, line_dash="solid", line_color="#475569", row=1, col=1)

    for col_idx in (1, 2, 3):
        fig.add_hline(
            y=spot_price, line_color="#38BDF8", line_width=2.2,
            row=1, col=col_idx,
        )

    if strikes.min() <= call_wall <= strikes.max():
        fig.add_hline(y=call_wall, line_color="#A855F7", line_dash="dash", line_width=1.8, row=1, col=1)
    if strikes.min() <= put_wall <= strikes.max():
        fig.add_hline(y=put_wall, line_color="#34D399", line_dash="dash", line_width=1.8, row=1, col=1)

    spot_label = f"◆ NQ FUTURES: {spot_price:,.1f}" if abs(spot_price - spot_mt5) < 0.1 else f"◆ SPOT CME: {spot_price:,.1f} (MT5: ~{spot_mt5:,.1f})"
    fig.add_annotation(
        x=0.98, y=spot_price,
        text=spot_label,
        showarrow=False, xanchor="right", xref="x domain", yref="y",
        font=dict(color="#FFFFFF", size=9.5, family="JetBrains Mono"),
        bgcolor="#0284C7", bordercolor="#38BDF8", borderwidth=1, borderpad=3,
        row=1, col=1,
    )

    if strikes.min() <= put_wall <= strikes.max():
        fig.add_annotation(
            x=0.03, y=put_wall - step * 0.15,
            text=f"<b>[PUT WALL {put_wall:,.0f}] ({put_wall_oi:,} OI)</b> &bull; Mua Rebound: {put_wall:,.0f}-{put_wall+15:,.0f} (SL: {put_wall-20:,.0f})",
            showarrow=True, arrowhead=2, arrowcolor="#EF4444", ax=0, ay=18,
            align="left", xref="x domain", yref="y",
            font=dict(color="#FEE2E2", size=8.5),
            bgcolor="rgba(127, 29, 29, 0.92)", bordercolor="#EF4444", borderwidth=1,
            row=1, col=1,
        )

    if strikes.min() <= strike_above <= strikes.max() and strike_above != call_wall:
        fig.add_annotation(
            x=0.03, y=strike_above + step * 0.15,
            text=f"<b>CỬA ẢI {strike_above:,.0f}</b> (Squeeze > {strike_above+buffer_val:,.1f} -> TP {next_above:,.0f})",
            showarrow=True, arrowhead=2, arrowcolor="#22C55E", ax=0, ay=-16,
            xref="x domain", yref="y", font=dict(color="#DCFCE7", size=8.5),
            bgcolor="rgba(20, 83, 45, 0.92)", bordercolor="#22C55E", borderwidth=1,
            row=1, col=1,
        )

    if strikes.min() <= strike_below <= strikes.max() and strike_below != put_wall and abs(strike_below - spot_price) > (step * 0.25):
        fig.add_annotation(
            x=0.03, y=strike_below - step * 0.15,
            text=f"<b>SÀN ĐỠ {strike_below:,.0f}</b> (Rebound: {strike_below-10:,.0f}-{strike_below+10:,.0f})",
            showarrow=True, arrowhead=2, arrowcolor="#38BDF8", ax=0, ay=16,
            xref="x domain", yref="y", font=dict(color="#E0F2FE", size=8.5),
            bgcolor="rgba(12, 74, 110, 0.92)", bordercolor="#38BDF8", borderwidth=1,
            row=1, col=1,
        )

    if strikes.min() <= secondary_support <= strikes.max() and secondary_support not in (put_wall, strike_below):
        fig.add_annotation(
            x=0.03, y=secondary_support - step * 0.15,
            text=f"<b>TRẠM NGHỈ {secondary_support:,.0f}</b> (TP Short / Đệm nấc 2 trước Put Wall {put_wall:,.0f})",
            showarrow=True, arrowhead=2, arrowcolor="#F59E0B", ax=0, ay=16,
            xref="x domain", yref="y", font=dict(color="#FEF3C7", size=8.5),
            bgcolor="rgba(180, 83, 9, 0.92)", bordercolor="#F59E0B", borderwidth=1,
            row=1, col=1,
        )

    fig.add_trace(
        go.Bar(
            y=df["strike"], x=df["callOpenInterest"], orientation="h",
            marker_color="#86EFAC", opacity=0.5, name="Call OI (Nền tích lũy)",
            hovertemplate="Strike: %{y:,.0f}<br>Call OI: %{x:,}<extra></extra>",
        ),
        row=1, col=2,
    )
    fig.add_trace(
        go.Bar(
            y=df["strike"], x=-df["putOpenInterest"], orientation="h",
            marker_color="#FCA5A5", opacity=0.5, name="Put OI (Nền tích lũy)",
            hovertemplate="Strike: %{y:,.0f}<br>Put OI: %{customdata:,}<extra></extra>",
            customdata=df["putOpenInterest"],
        ),
        row=1, col=2,
    )
    fig.add_trace(
        go.Bar(
            y=df["strike"], x=df["callVolume"], orientation="h",
            marker_color="#16A34A", name="Call Volume (Lực Mua)",
            hovertemplate="Strike: %{y:,.0f}<br>Call Vol: %{x:,}<extra></extra>",
        ),
        row=1, col=2,
    )
    fig.add_trace(
        go.Bar(
            y=df["strike"], x=-df["putVolume"], orientation="h",
            marker_color="#DC2626", name="Put Volume (Lực Bán)",
            hovertemplate="Strike: %{y:,.0f}<br>Put Vol: %{customdata:,}<extra></extra>",
            customdata=df["putVolume"],
        ),
        row=1, col=2,
    )
    fig.add_vline(x=0, line_dash="solid", line_color="#475569", row=1, col=2)

    fig.add_trace(
        go.Bar(
            y=df["strike"], x=df["netVEX"], orientation="h",
            marker_color="#FB923C", name="Net VEX ($M / 1% IV)",
            hovertemplate="Strike: %{y:,.0f}<br>Net VEX: $%{x:.2f}M<extra></extra>",
        ),
        row=1, col=3,
    )
    fig.add_trace(
        go.Bar(
            y=df["strike"], x=df["netCHEX"], orientation="h",
            marker_color="#22D3EE", name="Net CHEX ($M / ngày)",
            hovertemplate="Strike: %{y:,.0f}<br>Net CHEX: $%{x:.2f}M<extra></extra>",
        ),
        row=1, col=3,
    )
    fig.add_vline(x=0, line_dash="solid", line_color="#475569", row=1, col=3)

    top_vex_idx = df["netVEX"].abs().idxmax()
    top_vex_val = df.loc[top_vex_idx, "netVEX"]
    top_vex_stk = df.loc[top_vex_idx, "strike"]

    top_chex_idx = df["netCHEX"].abs().idxmax()
    top_chex_val = df.loc[top_chex_idx, "netCHEX"]
    top_chex_stk = df.loc[top_chex_idx, "strike"]

    if top_vex_stk == top_chex_stk:
        y_vex = top_vex_stk + step * 0.22
        y_chex = top_chex_stk - step * 0.22
    else:
        y_vex = top_vex_stk
        y_chex = top_chex_stk

    fig.add_annotation(
        x=top_vex_val, y=y_vex,
        text=f"◆ ĐỈNH VANNA ({top_vex_val:+.1f}M): V-Rebound",
        showarrow=False, xanchor="left" if top_vex_val >= 0 else "right",
        xref="x3", yref="y3", font=dict(color="#FDBA74", size=8.5),
        bgcolor="#1C1917", bordercolor="#FB923C", borderwidth=1, borderpad=2,
    )

    fig.add_annotation(
        x=top_chex_val, y=y_chex,
        text=f"ĐỈNH CHARM ({top_chex_val:+.1f}M): Ghìm giá đêm",
        showarrow=False, xanchor="right" if top_chex_val <= 0 else "left",
        xref="x3", yref="y3", font=dict(color="#67E8F9", size=8.5),
        bgcolor="#1C1917", bordercolor="#22D3EE", borderwidth=1, borderpad=2,
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0A0E17",
        plot_bgcolor="#111827",
        font=dict(family="Inter, sans-serif", color="#F8FAFC"),
        height=740,
        margin=dict(l=75, r=30, t=115, b=45),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.07,
            xanchor="center",
            x=0.5,
            font=dict(size=10),
        ),
        barmode="relative",
    )

    tickvals = list(strikes)
    ticktext = [f"{s:,.0f}" for s in strikes]
    fig.update_yaxes(
        tickmode="array", tickvals=tickvals, ticktext=ticktext,
        gridcolor="#1E293B", row=1, col=1,
        title=dict(text="E-mini Nasdaq Strike Ladder (NQ pts)", font=dict(size=11)),
    )
    fig.update_yaxes(tickmode="array", tickvals=tickvals, showticklabels=False, gridcolor="#1E293B", row=1, col=2)
    fig.update_yaxes(tickmode="array", tickvals=tickvals, showticklabels=False, gridcolor="#1E293B", row=1, col=3)

    fig.update_xaxes(gridcolor="#1E293B", title=dict(text="Net GEX ($M / 1% Move)", font=dict(size=10)), row=1, col=1)
    fig.update_xaxes(gridcolor="#1E293B", title=dict(text="Put OI/Vol (-) | Call OI/Vol (+)", font=dict(size=10)), row=1, col=2)

    max_vc = max(float(df["netVEX"].abs().max()), float(df["netCHEX"].abs().max()), 5.0)
    fig.update_xaxes(
        range=[-max_vc * 2.2, max_vc * 2.2],
        gridcolor="#1E293B",
        title=dict(text="Greeks Bậc 2 ($M Exposure)", font=dict(size=10)),
        row=1, col=3,
    )

    return fig


def generate_html_terminal(df: pd.DataFrame, meta: Dict[str, Any], fig: go.Figure) -> str:
    """Generate high-fidelity, standalone dark-mode HTML tactical report with True ATAS Orderflow Terminal."""
    now_vn = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
    now_str = now_vn.strftime("%d/%m/%Y %H:%M:%S")

    spot = meta["spot_price"]
    basis = meta["basis_offset"]
    spot_mt5 = meta["spot_mt5"]
    regime = meta["regime"]
    regime_desc = meta["regime_description"]
    total_gex = meta["total_net_gex"]
    total_vex = meta["total_net_vex"]
    total_chex = meta["total_net_chex"]
    expected_move = meta["expected_move_1s"]
    intraday_move = meta["intraday_rule16_move"]
    call_wall = meta["call_wall"]
    call_wall_oi = meta["call_wall_oi"]
    put_wall = meta["put_wall"]
    put_wall_oi = meta["put_wall_oi"]
    step = meta["step"]
    buffer_val = meta["buffer_val"]
    strike_above = meta["strike_above"]
    next_above = meta["next_above"]
    strike_below = meta["strike_below"]
    next_below = meta["next_below"]
    secondary_support = meta["secondary_support"]
    r_rate = meta.get("risk_free_rate", 0.0397)

    # Cost of Carry for Nasdaq Index (NQ Futures): F_theoretical = S_0 * exp((r - d) * T)
    div_yield_ndx = 0.0058  # Dividend yield rổ Nasdaq 100 ~ 0.58%
    dte_val = meta.get("dte_days", 1.0)
    t_carry = max(dte_val, 0.5) / 365.0
    spot_underlying = meta.get("spot_underlying_ndx", spot - basis if abs(basis) > 0.01 else spot - 12.5)
    f0_theoretical = spot_underlying * math.exp((r_rate - div_yield_ndx) * t_carry)
    delta_f = spot - f0_theoretical

    if delta_f > 3.0:
        delta_badge_class = "badge-pos"
        delta_status = "PREMIUM &bull; MUA ĐUỔI"
        delta_color = "#4ADE80"
    elif delta_f < -3.0:
        delta_badge_class = "badge-neg"
        delta_status = "DISCOUNT &bull; BÁN XẢ"
        delta_color = "#F87171"
    else:
        delta_badge_class = "badge-gold"
        delta_status = "FAIR VALUE &bull; CÂN BẰNG"
        delta_color = "#FACC15" 

    # Tactical Microstructure Ladder for 1M/5M ATAS Chart (25/50 pts grid centered around spot)
    tactical_step = 25.0
    atm_pivot = round(spot / tactical_step) * tactical_step
    buyer_abs_price = atm_pivot - 15.0 if spot >= atm_pivot else atm_pivot - 25.0
    seller_offer_price = atm_pivot + 15.0 if spot <= atm_pivot else atm_pivot + 25.0
    deep_ef_price = seller_offer_price + 25.0
    gex_react_price = atm_pivot + (5.0 if total_gex >= 0 else -5.0)
    charm_level_price = atm_pivot + (25.0 if total_chex >= 0 else -25.0)
    vanna_level_price = atm_pivot - (25.0 if total_vex <= 0 else -25.0)
    tactical_put_wall = atm_pivot - 50.0
    tactical_call_wall = atm_pivot + 50.0

    hard_sl_pts = min(step * 0.35, 25.0)
    fade_sl_pts = min(step * 0.30, 20.0)
    front_run_tp = max(1.0, step * 0.05)

    plotly_div = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"responsive": True, "displayModeBar": True})

    if "POSITIVE" in regime:
        regime_badge = '<span class="badge badge-pos" id="regime-badge">POSITIVE GAMMA (NÉN BIẾN ĐỘ / FADE)</span>'
        regime_color = "#4ADE80"
    elif "NEGATIVE" in regime:
        regime_badge = '<span class="badge badge-neg" id="regime-badge">NEGATIVE GAMMA (KHUẾCH ĐẠI / BREAKOUT)</span>'
        regime_color = "#F87171"
    else:
        regime_badge = '<span class="badge badge-gold" id="regime-badge">NEUTRAL TRANSITION (CÂN BẰNG)</span>'
        regime_color = "#FACC15"

    is_unified = abs(basis) < 0.01

    if is_unified:
        kpi_card_1 = f"""
        <div class="kpi-card">
            <div class="kpi-label">SPOT CME FUTURES (F0) &mdash; CME GLOBEX</div>
            <div class="kpi-val" style="color: #60A5FA;" id="kpi-spot-display">NQ <span id="kpi-spot-num">{spot:,.1f}</span></div>
            <div class="kpi-sub">F0 Lý Thuyết: <b id="kpi-fair-f0">{f0_theoretical:,.1f}</b> | Độ Lệch &Delta;F: <b id="kpi-delta-f" style="color: {delta_color};">{delta_f:+.1f} pts</b> (<span id="kpi-delta-status">{delta_status}</span>)</div>
        </div>
        """
        th_mt5 = ""
        td_mt5_1 = ""
        td_mt5_2 = ""
        td_mt5_3 = ""
        td_mt5_4 = ""
        td_mt5_5 = ""
        td_mt5_6 = ""
        col_cme_act = "Vùng Kích Hoạt (NQ)"
        col_cme_ent = "Entry NQ"
        col_cme_sl = "Hard SL (NQ)"
        micro_header = "📊 BẢNG DỮ LIỆU ĐỊNH LƯỢNG MICROSTRUCTURE TỪNG STRIKE (E-MINI NASDAQ FUTURES)"
    else:
        kpi_card_1 = f"""
        <div class="kpi-card">
            <div class="kpi-label">SPOT CME FUTURES &mdash; SPOT MT5 (Quy đổi)</div>
            <div class="kpi-val" style="color: #60A5FA;" id="kpi-spot-display">NQ <span id="kpi-spot-num">{spot:,.1f}</span> <span style="font-size: 15px; color: #38BDF8;">(MT5: ~<span id="kpi-mt5-num">{spot_mt5:,.1f}</span>)</span></div>
            <div class="kpi-sub">F0 Lý Thuyết: <b id="kpi-fair-f0">{f0_theoretical:,.1f}</b> | Độ Lệch &Delta;F: <b id="kpi-delta-f" style="color: {delta_color};">{delta_f:+.1f} pts</b> (<span id="kpi-delta-status">{delta_status}</span>)</div>
        </div>
        """
        th_mt5 = "<th>MT5 Spot (~ Basis)</th>"
        td_mt5_1 = f'<td style="color:#38BDF8; font-weight:600;">~{strike_above + buffer_val + 2.0 - basis:,.1f}</td>'
        td_mt5_2 = f'<td style="color:#38BDF8; font-weight:600;">~{strike_above - 2.0 - basis:,.1f}</td>'
        td_mt5_3 = f'<td style="color:#38BDF8; font-weight:600;">~{strike_below + 3.0 - basis:,.1f}</td>'
        td_mt5_4 = f'<td style="color:#38BDF8; font-weight:600;">~{strike_below - buffer_val - 2.0 - basis:,.1f}</td>'
        td_mt5_5 = f'<td style="color:#38BDF8; font-weight:600;">~{call_wall - 3.0 - basis:,.1f}</td>'
        td_mt5_6 = f'<td style="color:#38BDF8; font-weight:600;">~{put_wall + 3.0 - basis:,.1f}</td>'
        col_cme_act = "Vùng Kích Hoạt (CME)"
        col_cme_ent = "Entry CME"
        col_cme_sl = "Hard SL (CME)"
        micro_header = "📊 BẢNG DỮ LIỆU ĐỊNH LƯỢNG MICROSTRUCTURE TỪNG STRIKE (E-MINI NASDAQ & MT5 SPOT)"

    table_rows_html = ""

    js_options_data = []
    for _, r in df.sort_values("strike").iterrows():
        js_options_data.append({
            "strike": float(r["strike"]),
            "c_oi": int(r.get("callOpenInterest", 0)),
            "p_oi": int(r.get("putOpenInterest", 0)),
            "c_vol": int(r.get("callVolume", 0)),
            "p_vol": int(r.get("putVolume", 0)),
            "c_iv": float(round(clean_val(r.get("callIV", 0.18)), 4)),
            "p_iv": float(round(clean_val(r.get("putIV", 0.18)), 4)),
            "c_delta": float(round(clean_val(r.get("callDelta", 0.0)), 4)),
            "p_delta": float(round(clean_val(r.get("putDelta", 0.0)), 4)),
            "c_gamma": float(round(clean_val(r.get("callGamma", 0.0)), 6)),
            "p_gamma": float(round(clean_val(r.get("putGamma", 0.0)), 6)),
            "c_vega": float(round(clean_val(r.get("callVega", 0.0)), 4)),
            "p_vega": float(round(clean_val(r.get("putVega", 0.0)), 4)),
            "c_vanna": float(round(clean_val(r.get("callVanna", 0.0)), 6)),
            "p_vanna": float(round(clean_val(r.get("putVanna", 0.0)), 6)),
            "c_charm": float(round(clean_val(r.get("callCharm", 0.0)), 6)),
            "p_charm": float(round(clean_val(r.get("putCharm", 0.0)), 6)),
            "netGEX": float(round(clean_val(r.get("netGEX", 0.0)), 3)),
            "netVEX": float(round(clean_val(r.get("netVEX", 0.0)), 3)),
            "netCHEX": float(round(clean_val(r.get("netCHEX", 0.0)), 3)),
        })

    json_options_str = json.dumps(js_options_data)
    json_meta_str = json.dumps({
        "spot": spot,
        "basis": basis,
        "spot_mt5": spot_mt5,
        "step": step,
        "atm_strike": meta["atm_strike"],
        "call_wall": call_wall,
        "call_wall_oi": call_wall_oi,
        "put_wall": put_wall,
        "put_wall_oi": put_wall_oi,
        "tactical_call_wall": tactical_call_wall,
        "tactical_put_wall": tactical_put_wall,
        "buyer_abs": buyer_abs_price,
        "seller_offer": seller_offer_price,
        "deep_ef": deep_ef_price,
        "gex_react": gex_react_price,
        "charm_level": charm_level_price,
        "vanna_level": vanna_level_price,
        "strike_above": strike_above,
        "strike_below": strike_below,
        "next_above": next_above,
        "next_below": next_below,
        "secondary_support": secondary_support,
        "expected_move_1s": expected_move,
        "intraday_rule16_move": intraday_move,
        "total_net_gex": total_gex,
        "total_net_vex": total_vex,
        "total_net_chex": total_chex,
        "dte_days": meta.get("dte_days", 1.0),
        "risk_free_rate": r_rate,
        "effective_multiplier": meta.get("effective_multiplier", 20.0),
        "sigma_atm": meta.get("sigma_atm", 0.18),
        "f0_theoretical": float(round(f0_theoretical, 2)),
        "delta_f": float(round(delta_f, 2)),
        "div_yield": div_yield_ndx,
        "spot_underlying": float(round(spot_underlying, 2)),
    })

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>NEIRO-NQ-QUANT TERMINAL &bull; ATAS REALTIME QUANT ORDERFLOW</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        :root {{
            --bg-base: #000000; --bg-card: #0A0F18; --border-color: #141A24;
            --text-primary: #F8FAFC; --text-secondary: #94A3B8; --text-muted: #64748B;
            --neon-green: #22C55E; --neon-red: #EF4444; --neon-blue: #38BDF8; --neon-gold: #FACC15;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        html, body {{
            width: 100%; height: 100%; margin: 0; padding: 0;
            overflow: hidden; background-color: #000000;
            font-family: 'Inter', -apple-system, sans-serif;
            color: #F8FAFC;
        }}
        .atas-desktop-window {{
            display: flex; flex-direction: column;
            width: 100vw; height: 100vh;
            background-color: #000000;
            user-select: none;
        }}

        /* 100% Authentic ATAS Top Titlebar */
        .atas-win-topbar {{
            height: 34px; background: #161A22; border-bottom: 1px solid #232A37;
            display: flex; align-items: center; justify-content: space-between;
            padding: 0 8px; font-family: 'JetBrains Mono', monospace; font-size: 11px;
            flex-shrink: 0;
        }}
        .atas-top-left, .atas-top-center, .atas-top-right {{
            display: flex; align-items: center; gap: 5px;
        }}
        .atas-blue-indicator {{
            width: 4px; height: 18px; background: #0284C7; border-radius: 2px; margin-right: 3px;
        }}
        .atas-tab {{
            background: #202632; border: 1px solid #2F3849; color: #FFFFFF;
            padding: 3px 9px; border-radius: 4px; font-weight: 700; font-size: 11px;
            cursor: pointer;
        }}
        .atas-tab.active {{
            background: #252D3C; border-color: #38BDF8; color: #FFFFFF;
        }}
        .atas-win-sep {{ color: #3A4556; margin: 0 2px; font-size: 11px; }}
        .atas-btn-icon {{
            background: #202632; border: 1px solid #2F3849; color: #CBD5E1;
            padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;
            display: flex; align-items: center; gap: 4px;
        }}
        .atas-tf-group {{ display: flex; align-items: center; gap: 2px; }}
        .timeframe-pill {{
            background: transparent; color: #94A3B8; border: 1px solid transparent;
            padding: 2px 6px; border-radius: 3px; font-size: 11px; cursor: pointer; font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
        }}
        .timeframe-pill.active, .timeframe-pill:hover {{
            background: #2A3444; color: #38BDF8; border-color: #38BDF8;
        }}
        .atas-icon-btn {{
            background: transparent; border: 1px solid transparent; color: #94A3B8;
            padding: 3px 6px; border-radius: 3px; font-size: 11px; cursor: pointer;
            display: flex; align-items: center; gap: 3px; font-family: 'JetBrains Mono', monospace;
        }}
        .atas-icon-btn:hover {{ background: #202632; color: #E2E8F0; }}
        .atas-badge-contract {{
            background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.4);
            color: #38BDF8; padding: 2px 6px; border-radius: 3px; font-size: 10.5px; font-weight: 700;
        }}
        .atas-camera-btn {{
            background: #0284C7; color: #FFFFFF; border: none; padding: 3px 7px;
            border-radius: 4px; font-size: 11px; cursor: pointer; transition: all 0.2s;
        }}
        .atas-camera-btn:hover {{ background: #0369A1; }}

        /* Quantitative Top Metrics */
        .atas-quant-pill {{
            display: flex; align-items: center; gap: 6px; background: #10141C;
            border: 1px solid #1E2635; padding: 2px 8px; border-radius: 4px; font-size: 10.5px;
        }}
        .atas-sym-label {{ color: #64748B; font-size: 10px; font-weight: 600; }}
        .atas-price-val {{ font-size: 12px; font-weight: 800; }}
        .atas-mt5-tag {{ color: #64748B; font-size: 10px; }}
        .ticker-change {{ font-size: 10px; font-weight: 600; padding: 1px 4px; border-radius: 2px; }}
        .change-up {{ color: #4ADE80; background: rgba(34, 197, 94, 0.12); }}
        .change-down {{ color: #F87171; background: rgba(239, 68, 68, 0.12); }}
        .atas-pill-lbl {{ color: #64748B; font-size: 9.5px; }}
        .badge {{
            display: inline-block; padding: 1px 5px; border-radius: 2px; font-size: 10px;
            font-weight: 700; font-family: 'JetBrains Mono', monospace;
        }}
        .badge-live {{ background: rgba(34, 197, 94, 0.15); color: #4ADE80; border: 1px solid rgba(34, 197, 94, 0.4); }}
        .badge-gold {{ background: rgba(250, 204, 21, 0.15); color: #FACC15; border: 1px solid rgba(250, 204, 21, 0.4); }}
        .badge-pos {{ background: rgba(74, 222, 128, 0.15); color: #4ADE80; border: 1px solid rgba(74, 222, 128, 0.4); }}
        .badge-neg {{ background: rgba(248, 113, 113, 0.15); color: #F87171; border: 1px solid rgba(248, 113, 113, 0.4); }}

        /* Window Buttons */
        .win-btn {{
            width: 20px; height: 20px; display: flex; align-items: center; justify-content: center;
            background: #202632; border: 1px solid #2F3849; border-radius: 3px;
            color: #94A3B8; font-size: 9px; cursor: pointer;
        }}
        .win-btn:hover {{ background: #2F3849; color: #FFFFFF; }}
        .win-close:hover {{ background: #EF4444; color: #FFFFFF; border-color: #EF4444; }}

        /* Subbar Watermark */
        .atas-win-subbar {{
            height: 20px; background: #0B0E14; border-bottom: 1px solid #161D29;
            display: flex; align-items: center; justify-content: space-between;
            padding: 0 10px; font-family: 'JetBrains Mono', monospace; font-size: 10px;
            flex-shrink: 0;
        }}
        .atas-watermark-text {{ color: #475569; font-size: 9.5px; }}

        /* Body & Chart */
        .atas-body-container {{
            display: flex; flex: 1; width: 100%; height: calc(100vh - 58px);
            position: relative; overflow: hidden; background: #000000;
        }}
        .atas-left-tools {{
            width: 32px; background: #0B0E14; border-right: 1px solid #1A222F;
            display: flex; flex-direction: column; align-items: center; padding: 6px 0; gap: 8px;
            color: #64748B; font-size: 12px; z-index: 8; user-select: none; flex-shrink: 0;
        }}
        .tool-btn {{
            cursor: pointer; padding: 2px; border-radius: 3px; transition: all 0.2s;
            display: flex; align-items: center; justify-content: center; width: 22px; height: 22px;
        }}
        .tool-btn:hover, .tool-btn.active {{ color: #38BDF8; background: #1C2433; }}
        #tv-chart-wrapper {{
            position: relative; flex: 1; height: 100%; background-color: #000000;
        }}
        #atas-tv-chart {{ width: 100%; height: 100%; }}
        #atas-canvas {{
            position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            pointer-events: none; z-index: 5;
        }}

        /* Bottom Status */
        .atas-bottom-status {{
            height: 24px; background: #07090E; border-top: 1px solid #141A24;
            display: flex; justify-content: space-between; align-items: center;
            padding: 0 12px; font-family: 'JetBrains Mono', monospace; font-size: 10.5px; color: #64748B;
            flex-shrink: 0;
        }}
        .atas-logo-badge {{
            display: flex; align-items: center; gap: 6px; color: #94A3B8; font-weight: 700;
        }}
        .atas-vol-bar {{
            background: #0F172A; border: 1px solid #1E293B; height: 18px;
            padding: 0 12px; border-radius: 3px; display: flex; align-items: center;
            color: #60A5FA; font-weight: 700; font-size: 11px;
        }}
        .atas-floating-hud {{
            position: absolute; top: 8px; left: 10px; z-index: 10;
            display: flex; flex-direction: column; gap: 3px;
            background: rgba(6, 8, 13, 0.90); border: 1px solid #1E293B; border-radius: 4px;
            padding: 6px 10px; font-family: 'JetBrains Mono', monospace; font-size: 11px;
            pointer-events: none;
        }}
        .hud-item {{ display: flex; align-items: center; gap: 6px; white-space: nowrap; }}
        .hud-label {{ color: #94A3B8; font-weight: 600; font-size: 10.5px; min-width: 120px; }}
        .atas-win-topbar, .atas-win-subbar {{ overflow: hidden; white-space: nowrap; }}
        .atas-top-left, .atas-top-center, .atas-top-right {{ flex-shrink: 1; min-width: 0; overflow: hidden; }}
        .atas-subbar-right {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    </style>
</head>
<body>
<div class="atas-desktop-window" id="sec-atas">
    <!-- 100% Authentic ATAS Application Toolbar -->
    <div class="atas-win-topbar">
        <div class="atas-top-left">
            <span class="atas-blue-indicator"></span>
            <div class="atas-tab active"><span class="atas-tab-text">#NQZ6</span></div>
            <span class="atas-win-sep">|</span>
            <div class="atas-btn-icon"><span style="font-size:10px;">📈</span> 1 Lots</div>
            <span class="atas-win-sep">|</span>
            <div class="atas-tf-group">
                <button class="timeframe-pill" onclick="setTimeframe('5m')">M5</button>
                <button class="timeframe-pill" onclick="setTimeframe('1h')">H1</button>
                <button class="timeframe-pill" onclick="setTimeframe('d')">D</button>
                <button class="timeframe-pill active" onclick="setTimeframe('1m')">M1 ⌵</button>
            </div>
            <span class="atas-win-sep">|</span>
            <button class="atas-icon-btn" title="Indicators">📊 Indicators</button>
            <span class="atas-win-sep">|</span>
            <span class="atas-icon-btn" title="Mouse Mode">🖱️ 0</span>
            <span class="atas-icon-btn" title="Grid Layout">⊞</span>
            <span class="atas-icon-btn" title="DOM Trader">🗖 DOM Trader ⌵</span>
            <span class="atas-badge-contract">NQ 1m</span>
        </div>

        <!-- Center: Quantitative Metrics -->
        <div class="atas-top-center">
            <div class="atas-quant-pill">
                <span class="atas-sym-label">SPOT CME:</span>
                <b class="atas-price-val" id="top-ticker-price" style="color: #38BDF8;">{spot:,.2f}</b>
                <span class="ticker-change change-up" id="top-ticker-change">+0.00 (+0.00%)</span>
                <span class="atas-mt5-tag">(MT5: ~<span id="kpi-mt5-num">{spot_mt5:,.1f}</span>)</span>
                <span class="atas-win-sep">|</span>
                <span class="atas-pill-lbl">F0 FAIR:</span>
                <b id="top-ticker-f0-fair" style="color:#F1F5F9;">{f0_theoretical:,.1f}</b>
                <span class="atas-pill-lbl">&Delta;F:</span>
                <span id="top-ticker-delta-f" class="badge {delta_badge_class}">{delta_f:+.1f} pts</span>
                <span class="atas-win-sep">|</span>
                <span class="atas-pill-lbl">GEX:</span> <b id="kpi-gex-val" style="color:{regime_color};">${total_gex:+.1f}M</b>
                <span class="atas-pill-lbl">CHEX:</span> <b id="top-charm-val" style="color:#C084FC;">${total_chex:+.1f}M/d</b>
                <span class="atas-pill-lbl">VEX:</span> <b id="kpi-vex-val" style="color:#22D3EE;">${total_vex:+.1f}M</b>
                <span class="atas-pill-lbl">TEX:</span> <b id="top-theta-val" style="color:#FB923C;">--</b>
                <span class="atas-pill-lbl">SQZ:</span> <b style="color:#4ADE80;">&gt;{strike_above:,.0f}</b>/<b style="color:#F87171;">&lt;{strike_below:,.0f}</b>
                <span class="atas-pill-lbl">1-&sigma;:</span> <b id="kpi-move-val" style="color:#FACC15;">&plusmn;{expected_move:,.1f}p</b>
            </div>
        </div>

        <!-- Right: Authentic ATAS Controls -->
        <div class="atas-top-right">
            <span class="atas-icon-btn" title="Fullscreen">⛶</span>
            <span class="atas-icon-btn" title="Link Symbol">🔗</span>
            <button class="atas-camera-btn" title="Snapshot" onclick="alert('ATAS Snapshot captured')">📷</button>
            <span class="atas-icon-btn" title="Calendar">📅</span>
            <span class="atas-icon-btn" style="color: #E2E8F0; font-weight:700;">ETH</span>
            <span class="atas-win-sep">|</span>
            <button class="win-btn" title="Settings">⚙</button>
            <span class="win-btn win-min" title="Minimize">—</span>
            <span class="win-btn win-close" title="Close">✕</span>
        </div>
    </div>

    <!-- Authentic ATAS Subbar Watermark -->
    <div class="atas-win-subbar">
        <div class="atas-subbar-left">
            <span class="atas-watermark-text">NEIRO-NQ-QUANT TERMINAL &bull; TradingPlatform by Rithmic™ &bull; Powered by OMNE™</span>
        </div>
        <div class="atas-subbar-right">
            <span style="color:#38BDF8; font-weight:700;">⚡ LIVE BLACK-76 REALTIME GREEKS RADAR:</span>
            <span id="live-greeks-radar" style="margin-left: 6px; color: #CBD5E1;">
                Delta &Delta;: <b>0.505</b> | Gamma &Gamma;: <b>0.00042</b> | Vega &nu;: <b>$18.5M</b> | Theta &theta;: <b>-$28.5k/d</b> | Vanna (VEX): <b>+$2.8M</b> | Charm (CHEX): <b>-$1.4M/d</b>
            </span>
            <span style="color:#64748B; margin-left: 8px;">| ATM: <b id="top-ticker-atm">{meta['atm_strike']:,.0f} pts</b> | IV: <b id="top-ticker-iv">{meta.get('sigma_atm', 0.18)*100:.1f}%</b> | r: <b>{r_rate*100:.2f}%</b></span>
        </div>
    </div>

    <!-- Main ATAS Body -->
    <div class="atas-body-container">
        <!-- Authentic ATAS Left Drawing Toolbar -->
        <div class="atas-left-tools">
            <span class="tool-btn active" title="Con trỏ">✛</span>
            <span class="tool-btn" title="Đường xu hướng">╱</span>
            <span class="tool-btn" title="Tia ngang">━</span>
            <span class="tool-btn" title="Mũi tên">↗</span>
            <span class="tool-btn" title="Vẽ tự do">✎</span>
            <span class="tool-btn" title="Văn bản">T</span>
            <span class="tool-btn" title="Hộp vùng cản">▭</span>
            <span class="tool-btn" title="Thước đo">📏</span>
            <div style="flex: 1;"></div>
            <span class="tool-btn" title="Cài đặt">⚙</span>
        </div>

        <div id="tv-chart-wrapper">
            <div class="atas-floating-hud">
                <div class="hud-item"><span class="hud-label">GEX (Net Gamma):</span> <b id="hud-gex-val" style="color:{regime_color};">${total_gex:+.1f}M</b></div>
                <div class="hud-item"><span class="hud-label">GAMMA SQUEEZE &uarr;:</span> <b style="color:#4ADE80;">&gt; {strike_above:,.0f} &rarr; TP {next_above:,.0f}</b></div>
                <div class="hud-item"><span class="hud-label">GAMMA SQUEEZE &darr;:</span> <b style="color:#F87171;">&lt; {strike_below:,.0f} &rarr; TP {next_below:,.0f}</b></div>
                <div class="hud-item"><span class="hud-label">VANNA (VEX):</span> <b id="hud-vanna-val" style="color:#22D3EE;">${total_vex:+.1f}M</b></div>
                <div class="hud-item"><span class="hud-label">CHARM (CHEX):</span> <b id="hud-charm-val" style="color:#C084FC;">${total_chex:+.1f}M/d</b></div>
                <div class="hud-item"><span class="hud-label">THETA (TEX):</span> <b id="hud-theta-val" style="color:#FB923C;">--</b></div>
                <div class="hud-item"><span class="hud-label">1-SIGMA:</span> <b id="hud-sigma-val" style="color:#FACC15;">&plusmn;{expected_move:,.1f}p</b></div>
            </div>
            <div id="atas-tv-chart"></div>
            <canvas id="atas-canvas"></canvas>
        </div>
    </div>

    <!-- Bottom Status Bar -->
    <div class="atas-bottom-status">
        <div class="atas-logo-badge">
            <span style="color:#38BDF8; font-weight:800;">ATAS</span>
            <span style="color:#94A3B8;">TrueVision Levels &bull; 11h [+]</span>
            <span style="color:#475569; font-size:9.5px; margin-left:8px;">Cập nhật: {now_str} (VN)</span>
        </div>
        <div style="display:flex; align-items:center; gap:10px;">
            <span style="color:#475569; font-size:10px;">CME GLOBEX</span>
            <div class="atas-vol-bar">32793639</div>
        </div>
    </div>
</div>

<script>
window.INITIAL_OPTIONS = {json_options_str};
window.INITIAL_META = {json_meta_str};

// ----------------------------------------------------------------------------
// Client-Side Black-76 Greeks & Quant Engine (JavaScript)
// ----------------------------------------------------------------------------
const Black76Engine = {{
    normalCdf(x) {{
        const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741;
        const a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
        const sign = x < 0 ? -1 : 1;
        const absX = Math.abs(x) / Math.SQRT2;
        const t = 1.0 / (1.0 + p * absX);
        const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-absX * absX);
        return 0.5 * (1.0 + sign * y);
    }},

    normalPdf(x) {{
        return Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI);
    }},

    calcGreeks(F, K, T, r, sigma, isCall) {{
        if (T <= 0.0001 || sigma <= 0.0001 || F <= 0 || K <= 0) {{
            return {{ delta: 0, gamma: 0, vega: 0, theta: 0, vanna: 0, charm: 0 }};
        }}
        const sqrtT = Math.sqrt(T);
        const d1 = (Math.log(F / K) + 0.5 * sigma * sigma * T) / (sigma * sqrtT);
        const d2 = d1 - sigma * sqrtT;
        const df = Math.exp(-r * T);
        const n_d1 = this.normalCdf(d1);
        const np_d1 = this.normalPdf(d1);

        const delta = isCall ? df * n_d1 : -df * this.normalCdf(-d1);
        const gamma = (df * np_d1) / (F * sigma * sqrtT);
        const vega = F * df * np_d1 * sqrtT;

        const theta_term1 = -(F * df * np_d1 * sigma) / (2 * sqrtT);
        const theta = isCall
            ? (theta_term1 + r * df * (F * n_d1 - K * this.normalCdf(d2))) / 365.0
            : (theta_term1 - r * df * (F * this.normalCdf(-d1) - K * this.normalCdf(-d2))) / 365.0;

        const vanna = -df * np_d1 * (d2 / sigma);
        const charm = isCall
            ? df * (r * n_d1 - np_d1 * ((2 * r * T - d2 * sigma * sqrtT) / (2 * T * sigma * sqrtT)))
            : -df * (r * this.normalCdf(-d1) + np_d1 * ((2 * r * T - d2 * sigma * sqrtT) / (2 * T * sigma * sqrtT)));

        return {{ delta, gamma, vega, theta, vanna, charm }};
    }},

    recalculate(F, options, meta) {{
        const T = Math.max(0.0005, (meta.dte_days || 1.0) / 365.0);
        const r = meta.risk_free_rate || 0.0397;
        const mult = meta.effective_multiplier || 20.0;
        const scale_gex = (F * F) * 0.01 / 1e6;
        const scale_vex = F * 0.01 / 1e6;
        const scale_chex = F / 1e6;

        let totalGEX = 0.0;
        let totalVEX = 0.0;
        let totalCHEX = 0.0;
        let totalTEX = 0.0;
        let totalVega = 0.0;
        let atmStrike = options[0].strike;
        let minDiff = 999999;
        let atmGreeks = null;
        let atmIV = 0.18;

        for (let i = 0; i < options.length; i++) {{
            const row = options[i];
            const K = row.strike;
            const diff = Math.abs(K - F);
            if (diff < minDiff) {{
                minDiff = diff;
                atmStrike = K;
                atmIV = (row.c_iv + row.p_iv) / 2.0;
            }}

            const cG = this.calcGreeks(F, K, T, r, row.c_iv, true);
            const pG = this.calcGreeks(F, K, T, r, row.p_iv, false);

            const cGEX = cG.gamma * row.c_oi * mult * scale_gex;
            const pGEX = -(pG.gamma * row.p_oi * mult * scale_gex);
            const netGEX = cGEX + pGEX;
            totalGEX += netGEX;

            const cVEX = cG.vanna * row.c_oi * mult * scale_vex;
            const pVEX = -(pG.vanna * row.p_oi * mult * scale_vex);
            const netVEX = cVEX + pVEX;
            totalVEX += netVEX;

            const cCHEX = (cG.charm / 365.0) * row.c_oi * mult * scale_chex;
            const pCHEX = -((pG.charm / 365.0) * row.p_oi * mult * scale_chex);
            const netCHEX = cCHEX + pCHEX;
            totalCHEX += netCHEX;

            // Theta exposure: $M/day decay of open interest (points/day x multiplier x OI)
            const netTEX = (cG.theta * row.c_oi + pG.theta * row.p_oi) * mult / 1e6;
            totalTEX += netTEX;
            totalVega += (cG.vega * row.c_oi + pG.vega * row.p_oi) * mult * 0.01 / 1e6;
            row.currentNetTEX = netTEX;
            row.currentNetGEX = netGEX;
            row.currentNetVEX = netVEX;
            row.currentNetCHEX = netCHEX;

            if (K === atmStrike) {{
                atmGreeks = {{
                    delta: cG.delta,
                    gamma: cG.gamma,
                    vega: cG.vega * 0.01,
                    theta: (cG.theta + pG.theta) / 2.0,
                    vanna: totalVEX,
                    charm: totalCHEX
                }};
            }}
        }}

        const expectedMove = F * atmIV * Math.sqrt(T);
        const intradayMove = (F * atmIV) / 16.0;

        return {{
            spot: F,
            totalGEX,
            totalVEX,
            totalCHEX,
            totalTEX,
            totalVega,
            atmStrike,
            atmIV,
            expectedMove,
            intradayMove,
            atmGreeks: atmGreeks || {{ delta: 0.505, gamma: 0.00042, vega: 18.5, theta: -28.5, vanna: 2.8, charm: -1.4 }}
        }};
    }}
}};

// ----------------------------------------------------------------------------
// TradingView Lightweight Charts & ATAS Orderflow Integration
// ----------------------------------------------------------------------------
let chart = null;
let candleSeries = null;
let livePriceLine = null;
let currentPrice = window.INITIAL_META.spot;
const initialBasePrice = window.INITIAL_META.spot;
let isSimulating = false; // Default OFF: Stands still on CME official close
let simInterval = null;
let lastCandle = null;
let currentTimeframe = '1m';
let currentPeriod = 60; // 60s default for 1M
let clusterBubbles = [];
let anchoredZones = [];
let volumeProfileBins = [];

// Brownian-Bridge Candlestick Generator: Smooth realistic 1M walk ending EXACTLY at currentP
function generateRealisticCandles(currentP, numBars = 60, periodSec = 60) {{
    const bars = [];
    const nowSec = Math.floor(Date.now() / 1000);
    const startSec = nowSec - (numBars * periodSec);

    const increments = [];
    let sum = 0;
    const vol = 1.25 * Math.sqrt(periodSec / 60);
    for (let i = 0; i < numBars; i++) {{
        const r = (Math.random() - 0.49) * 2.0 * vol;
        increments.push(r);
        sum += r;
    }}

    const targetDrift = (Math.random() - 0.5) * 6.0;
    const startP = currentP - targetDrift;
    const correction = (targetDrift - sum) / numBars;

    let p = startP;
    clusterBubbles = [];

    for (let i = 0; i < numBars; i++) {{
        const t = startSec + i * periodSec;
        const change = increments[i] + correction;
        const open = Math.round(p * 4) / 4;
        const close = Math.round((p + change) * 4) / 4;
        const high = Math.round((Math.max(open, close) + Math.random() * vol * 0.9) * 4) / 4;
        const low = Math.round((Math.min(open, close) - Math.random() * vol * 0.9) * 4) / 4;
        p = close;
        const barTime = t - (t % periodSec);
        bars.push({{ time: barTime, open, high, low, close }});

        // Generate authentic ATAS blue and gold footprint cluster bubbles along reversal candles
        if (i >= numBars - 24 && (i % 2 === 0 || i >= numBars - 6)) {{
            const clusterCounts = [4, 5, 3, 6, 4];
            const numPills = clusterCounts[i % clusterCounts.length];
            const stepY = (high - low) / (numPills + 1);
            const sampleVols = [33, 52, 30, 40, 41, 51, 42, 43, 50, 54, 46, 55, 65, 36, 35, 59, 37, 30, 35, 37];
            for (let k = 0; k < numPills; k++) {{
                const v = sampleVols[(i * 3 + k) % sampleVols.length];
                const isGold = (v >= 42); // Ochre/gold for high absorption, dark blue for Delta
                clusterBubbles.push({{
                    time: barTime,
                    price: low + stepY * (k + 1),
                    vol: v,
                    isGold: isGold
                }});
            }}
        }}
    }}

    // ATAS anchored orderflow zones: each zone accompanies specific candles (đi theo từng nến)
    anchoredZones = [];
    const zoneDefs = [
        {{ idx: numBars - 24, endIdx: numBars - 20, label: 'deep ef stack', side: 'high', oval: true }},
        {{ idx: numBars - 21, endIdx: numBars - 18, label: '',              side: 'high', oval: true }},
        {{ idx: numBars - 18, endIdx: numBars - 13, label: 'buyer abs',     side: 'low',  oval: true }},
        {{ idx: numBars - 11, endIdx: numBars - 6,  label: 'seller offer',  side: 'high', oval: true, tag: '+1R' }},
        {{ idx: numBars - 6,  endIdx: numBars - 2,  label: '',              side: 'low',  oval: false }},
    ];
    zoneDefs.forEach(z => {{
        const b = bars[z.idx];
        const bEnd = bars[z.endIdx] || bars[bars.length - 1];
        if (!b) return;
        const bodyTop = Math.max(b.open, b.close);
        const bodyBot = Math.min(b.open, b.close);
        const top = z.side === 'high' ? b.high : bodyBot + 1.25;
        const bot = z.side === 'high' ? Math.max(bodyTop - 1.25, b.low) : b.low;
        anchoredZones.push({{
            time: b.time,
            endTime: bEnd ? bEnd.time : null,
            top: Math.max(top, bot + 1.0),
            bottom: bot,
            label: z.label,
            oval: z.oval,
            tag: z.tag || '',
            side: z.side
        }});
    }});

    bars[bars.length - 1].close = currentP;
    bars[bars.length - 1].high = Math.max(bars[bars.length - 1].high, currentP);
    bars[bars.length - 1].low = Math.min(bars[bars.length - 1].low, currentP);

    // Left Volume Profile bins
    volumeProfileBins = [];
    const minP = currentP - 50.0;
    const maxP = currentP + 50.0;
    for (let pStep = minP; pStep <= maxP; pStep += 2.5) {{
        volumeProfileBins.push({{
            price: pStep,
            volume: Math.floor(40 + Math.random() * 110)
        }});
    }}

    return bars;
}}

function initAtasChart() {{
    const container = document.getElementById('atas-tv-chart');
    const canvas = document.getElementById('atas-canvas');
    if (!container || !window.LightweightCharts) return;

    chart = LightweightCharts.createChart(container, {{
        width: container.clientWidth,
        height: container.clientHeight || (window.innerHeight - 62),
        layout: {{
            background: {{ type: 'solid', color: '#000000' }},
            textColor: '#94A3B8',
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 11,
        }},
        grid: {{
            vertLines: {{ color: '#0A0F18' }},
            horzLines: {{ color: '#0A0F18' }},
        }},
        crosshair: {{
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {{ color: '#38BDF8', width: 1, style: 3 }},
            horzLine: {{ color: '#38BDF8', width: 1, style: 3 }},
        }},
        rightPriceScale: {{
            borderColor: '#1E293B',
            scaleMargins: {{ top: 0.10, bottom: 0.10 }},
        }},
        timeScale: {{
            borderColor: '#1E293B',
            timeVisible: true,
            secondsVisible: false,
            barSpacing: 22,
            minBarSpacing: 10,
            rightOffset: 12,
        }},
    }});

    candleSeries = chart.addCandlestickSeries({{
        upColor: 'rgba(28, 34, 46, 0.75)',
        downColor: 'rgba(28, 34, 46, 0.75)',
        borderVisible: true,
        borderUpColor: '#A1A1AA',
        borderDownColor: '#71717A',
        wickUpColor: '#A1A1AA',
        wickDownColor: '#71717A',
    }});

    buildHistoricalBars(60);

    livePriceLine = candleSeries.createPriceLine({{
        price: currentPrice,
        color: '#F43F5E',
        lineWidth: 2,
        lineStyle: LightweightCharts.LineStyle.Solid,
        axisLabelVisible: true,
        title: 'F0 LIVE',
    }});

    const initialH = container.clientHeight || (window.innerHeight - 62);
    if (canvas) {{
        canvas.width = container.clientWidth;
        canvas.height = initialH;
    }}

    window.addEventListener('resize', () => {{
        const newH = container.clientHeight || (window.innerHeight - 62);
        chart.applyOptions({{ width: container.clientWidth, height: newH }});
        if (canvas) {{
            canvas.width = container.clientWidth;
            canvas.height = newH;
        }}
        drawAtasOverlay();
    }});

    chart.timeScale().subscribeVisibleTimeRangeChange(() => drawAtasOverlay());
    chart.timeScale().subscribeVisibleLogicalRangeChange(() => drawAtasOverlay());

    drawAtasOverlay();
}}

function buildHistoricalBars(periodSec = 60) {{
    currentPeriod = periodSec;
    const bars = generateRealisticCandles(currentPrice, 60, periodSec);
    lastCandle = bars[bars.length - 1];
    candleSeries.setData(bars);
    const totalBars = bars.length;
    chart.timeScale().setVisibleLogicalRange({{
        from: totalBars - 32,
        to: totalBars + 8,
    }});
    setTimeout(() => drawAtasOverlay(), 80);
}}

// ----------------------------------------------------------------------------
// ATAS Orderflow Canvas Drawing Engine
// ----------------------------------------------------------------------------
function drawAtasOverlay() {{
    const canvas = document.getElementById('atas-canvas');
    if (!canvas || !chart || !candleSeries) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    const m = window.INITIAL_META;

    // 1. Left Volume Profile Histogram (purple/slate bars)
    if (volumeProfileBins && volumeProfileBins.length > 0) {{
        volumeProfileBins.forEach(bin => {{
            const y = candleSeries.priceToCoordinate(bin.price);
            if (y !== null && y >= 0 && y <= h) {{
                const barW = Math.min(65, bin.volume * 0.45);
                ctx.fillStyle = 'rgba(99, 102, 241, 0.22)';
                ctx.fillRect(4, y - 2, barW, 4);
                ctx.fillStyle = 'rgba(129, 140, 248, 0.50)';
                ctx.fillRect(4, y - 2, barW * 0.4, 4);
            }}
        }});
    }}

    // 2. Exact ATAS Orderflow Shaded Zones (matching atas_crop_boxes.png)
    const startX = Math.max(80, Math.floor(w * 0.30));
    const rightX = w - 75;
    const boxW = Math.max(100, rightX - startX);

    // A. Put Wall Dotted Line (Yellow)
    const yPw = candleSeries.priceToCoordinate(m.tactical_put_wall || (m.spot + 20.0));
    if (yPw !== null && yPw >= 0 && yPw <= h) {{
        ctx.strokeStyle = '#FACC15';
        ctx.setLineDash([2, 3]);
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(80, yPw);
        ctx.lineTo(rightX, yPw);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = '#FEF08A';
        ctx.font = '10px "JetBrains Mono", monospace';
        ctx.textAlign = 'right';
        ctx.fillText('..... Put wall · Gamma C · Gamma P · DEX P · #1 · OI put ' + (m.put_wall_oi || 31287).toLocaleString(), rightX - 5, yPw - 4);
    }}

    // B. ATAS orderflow zones: tightly accompanying specific candles (đi theo từng nến)
    anchoredZones.forEach(z => {{
        const x0 = chart.timeScale().timeToCoordinate(z.time);
        const x1 = z.endTime ? chart.timeScale().timeToCoordinate(z.endTime) : null;
        const yT = candleSeries.priceToCoordinate(z.top);
        const yB = candleSeries.priceToCoordinate(z.bottom);
        if (x0 === null || yT === null || yB === null) return;
        const top = Math.min(yT, yB);
        const hz = Math.max(7, Math.abs(yB - yT));
        const xs = x0 - 8;
        const xe = (x1 !== null && x1 > x0) ? (x1 + 8) : (x0 + 38);
        const wBox = Math.max(22, Math.min(xe - xs, rightX - xs - 8));

        // 1. Shaded orderflow absorption block tightly bounding these candles
        ctx.fillStyle = 'rgba(148, 163, 184, 0.28)';
        ctx.fillRect(xs, top, wBox, hz);
        ctx.strokeStyle = 'rgba(203, 213, 225, 0.55)';
        ctx.lineWidth = 1;
        ctx.strokeRect(xs, top, wBox, hz);

        // 2. Red oval circling the trigger candle footprint cluster at x0
        if (z.oval) {{
            ctx.strokeStyle = 'rgba(239, 68, 68, 0.92)';
            ctx.lineWidth = 1.6;
            ctx.beginPath();
            ctx.ellipse(x0, top + hz / 2, 14, Math.max(8, hz / 2 + 3), 0, 0, Math.PI * 2);
            ctx.stroke();
        }}

        // 3. Label badge placed directly at candle x0
        if (z.label) {{
            ctx.font = 'bold 10px "JetBrains Mono", monospace';
            const tw = ctx.measureText(z.label).width;
            const ly = z.side === 'high' ? (top - 8) : (top + hz + 14);
            ctx.fillStyle = 'rgba(15, 23, 42, 0.90)';
            ctx.fillRect(x0 - tw / 2 - 4, ly - 10, tw + 8, 14);
            ctx.strokeStyle = 'rgba(148, 163, 184, 0.5)';
            ctx.strokeRect(x0 - tw / 2 - 4, ly - 10, tw + 8, 14);
            ctx.fillStyle = '#FFFFFF';
            ctx.textAlign = 'center';
            ctx.fillText(z.label, x0, ly);
        }}

        // 4. Tag (+1R) placed right at candle x0
        if (z.tag) {{
            ctx.font = 'bold 9.5px "JetBrains Mono", monospace';
            const ty = z.side === 'high' ? (top - 23) : (top + hz + 28);
            ctx.fillStyle = '#38BDF8';
            ctx.textAlign = 'center';
            ctx.fillText(z.tag, x0, ty);
        }}
    }});

    // F. gex 5 reaction (White outlined box)
    const yGex = candleSeries.priceToCoordinate(m.gex_react || (m.spot - 15.0));
    if (yGex !== null && yGex >= 0 && yGex <= h) {{
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
        ctx.lineWidth = 1;
        ctx.strokeRect(80, yGex - 8, rightX - 80, 16);

        ctx.fillStyle = '#FFFFFF';
        ctx.font = 'bold 11px "JetBrains Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('gex 5 reaction', startX + (boxW / 2), yGex + 4);

        // Bottom dotted level #5 31246.00
        ctx.strokeStyle = '#FACC15';
        ctx.setLineDash([2, 3]);
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(80, yGex + 18);
        ctx.lineTo(rightX, yGex + 18);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = '#FACC15';
        ctx.font = '10px "JetBrains Mono", monospace';
        ctx.textAlign = 'right';
        ctx.fillText('#5 ' + (m.gex_react - 5).toFixed(2), rightX - 5, yGex + 15);
    }}

    // F2. Key Greeks levels: Call/Put Wall, Gamma Flip, Gamma Squeeze, Vanna, Charm
    const keyLevels = [
        {{ p: m.tactical_call_wall || m.call_wall, c: '#EF4444', d: [6, 4], txt: 'CALL WALL ' + Math.round(m.tactical_call_wall || m.call_wall) + ' · OI ' + (m.call_wall_oi || 0).toLocaleString() }},
        {{ p: m.tactical_put_wall || m.put_wall,   c: '#22C55E', d: [6, 4], txt: 'PUT WALL ' + Math.round(m.tactical_put_wall || m.put_wall) + ' · OI ' + (m.put_wall_oi || 0).toLocaleString() }},
        {{ p: m.strike_above,                      c: '#4ADE80', d: [2, 3], txt: 'GAMMA SQUEEZE ↑ > ' + Math.round(m.strike_above) + ' → TP ' + Math.round(m.next_above) }},
        {{ p: m.strike_below,                      c: '#F87171', d: [2, 3], txt: 'GAMMA SQUEEZE ↓ < ' + Math.round(m.strike_below) + ' → TP ' + Math.round(m.next_below) }},
        {{ p: m.vanna_level,                       c: '#22D3EE', d: [6, 3], txt: 'VANNA (VEX) · V-REBOUND · ' + (m.total_net_vex || 0).toFixed(1) + 'M' }},
        {{ p: m.charm_level,                       c: '#C084FC', d: [6, 3], txt: 'CHARM (CHEX) · GHIM GIÁ ĐÊM · ' + (m.total_net_chex || 0).toFixed(1) + 'M/d' }},
        {{ p: m.gex_react,                         c: '#FACC15', d: [3, 3], txt: 'GAMMA FLIP (Trục cân đối) ' + Math.round(m.gex_react) }},
    ];
    keyLevels.forEach(L => {{
        if (!L.p) return;
        const y = candleSeries.priceToCoordinate(L.p);
        if (y !== null && y >= 0 && y <= h) {{
            // Inside viewport: draw full dashed level line with right contrast tag
            ctx.strokeStyle = L.c;
            ctx.setLineDash(L.d);
            ctx.lineWidth = 1.3;
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(rightX, y);
            ctx.stroke();
            ctx.setLineDash([]);

            ctx.font = 'bold 10px "JetBrains Mono", monospace';
            ctx.textAlign = 'right';
            const tw = ctx.measureText(L.txt).width;
            ctx.fillStyle = 'rgba(6, 8, 14, 0.88)';
            ctx.fillRect(rightX - tw - 12, y - 14, tw + 10, 13);
            ctx.strokeStyle = L.c;
            ctx.lineWidth = 1;
            ctx.strokeRect(rightX - tw - 12, y - 14, tw + 10, 13);
            ctx.fillStyle = L.c;
            ctx.fillText(L.txt, rightX - 7, y - 4);
        }} else if (y !== null && y < 0) {{
            // Above viewport: draw pinned top edge indicator
            const edgeY = 16;
            ctx.font = 'bold 9.5px "JetBrains Mono", monospace';
            ctx.textAlign = 'right';
            const shortTxt = '▲ ' + L.txt.split('·')[0];
            const tw = ctx.measureText(shortTxt).width;
            ctx.fillStyle = 'rgba(15, 23, 42, 0.92)';
            ctx.fillRect(rightX - tw - 14, edgeY - 11, tw + 10, 14);
            ctx.strokeStyle = L.c;
            ctx.lineWidth = 1;
            ctx.strokeRect(rightX - tw - 14, edgeY - 11, tw + 10, 14);
            ctx.fillStyle = L.c;
            ctx.fillText(shortTxt, rightX - 9, edgeY);
        }} else if (y !== null && y > h) {{
            // Below viewport: draw pinned bottom edge indicator
            const edgeY = h - 8;
            ctx.font = 'bold 9.5px "JetBrains Mono", monospace';
            ctx.textAlign = 'right';
            const shortTxt = '▼ ' + L.txt.split('·')[0];
            const tw = ctx.measureText(shortTxt).width;
            ctx.fillStyle = 'rgba(15, 23, 42, 0.92)';
            ctx.fillRect(rightX - tw - 14, edgeY - 11, tw + 10, 14);
            ctx.strokeStyle = L.c;
            ctx.lineWidth = 1;
            ctx.strokeRect(rightX - tw - 14, edgeY - 11, tw + 10, 14);
            ctx.fillStyle = L.c;
            ctx.fillText(shortTxt, rightX - 9, edgeY);
        }}
    }});

    // F3. Per-strike Greeks exposure profile (GEX | VEX | CHEX | THETA)
    const opts = window.INITIAL_OPTIONS || [];
    if (opts.length && opts[0].currentNetGEX !== undefined) {{
        const cols = [
            {{ key: 'currentNetGEX',  name: 'GEX',   pos: '#22C55E', neg: '#EF4444' }},
            {{ key: 'currentNetVEX',  name: 'VEX',   pos: '#22D3EE', neg: '#0E7490' }},
            {{ key: 'currentNetCHEX', name: 'CHEX',  pos: '#C084FC', neg: '#7E22CE' }},
            {{ key: 'currentNetTEX',  name: 'THETA', pos: '#FDBA74', neg: '#EA580C' }},
        ];
        const colW = 62;
        const panelX = rightX - cols.length * colW - 8;
        ctx.fillStyle = 'rgba(5, 7, 11, 0.72)';
        ctx.fillRect(panelX - 4, 0, cols.length * colW + 8, h);
        cols.forEach((c, ci) => {{
            const cx = panelX + ci * colW + colW / 2;
            let maxAbs = 1e-9;
            opts.forEach(o => {{ maxAbs = Math.max(maxAbs, Math.abs(o[c.key] || 0)); }});
            ctx.strokeStyle = 'rgba(148, 163, 184, 0.25)';
            ctx.beginPath(); ctx.moveTo(cx, 18); ctx.lineTo(cx, h); ctx.stroke();
            ctx.fillStyle = '#94A3B8';
            ctx.font = 'bold 10px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.fillText(c.name, cx, 12);
            opts.forEach(o => {{
                const y = candleSeries.priceToCoordinate(o.strike);
                const v = o[c.key] || 0;
                if (y === null || y < 18 || y > h - 4 || v === 0) return;
                const len = (Math.abs(v) / maxAbs) * (colW / 2 - 4);
                ctx.fillStyle = v >= 0 ? c.pos : c.neg;
                ctx.fillRect(v >= 0 ? cx : cx - len, y - 2.5, len, 5);
            }});
        }});
    }}

    // G. Right Axis Volume Histogram Bars (ATAS tick ladder volume)
    const rightTicks = [
        {{ offset: 25.0, w: 26, isBlue: false }},
        {{ offset: 20.0, w: 38, isBlue: true }},
        {{ offset: 15.0, w: 18, isBlue: false }},
        {{ offset: 10.0, w: 45, isBlue: true }},
        {{ offset: 5.0, w: 12, isBlue: false }},
        {{ offset: -2.5, w: 22, isBlue: false }},
        {{ offset: -7.5, w: 34, isBlue: true }},
        {{ offset: -12.5, w: 48, isBlue: true }},
        {{ offset: -17.5, w: 15, isBlue: false }},
        {{ offset: -22.5, w: 30, isBlue: true }},
        {{ offset: -27.5, w: 42, isBlue: true }},
    ];
    rightTicks.forEach(t => {{
        const y = candleSeries.priceToCoordinate(currentPrice + t.offset);
        if (y !== null && y >= 0 && y <= h) {{
            ctx.fillStyle = t.isBlue ? 'rgba(56, 189, 248, 0.85)' : 'rgba(255, 255, 255, 0.85)';
            ctx.fillRect(rightX, y - 1.5, t.w, 3);
        }}
    }});

    // 3. Authentic ATAS Blue and Gold Footprint Cluster Bubbles
    if (clusterBubbles && clusterBubbles.length > 0) {{
        clusterBubbles.forEach(cb => {{
            const x = chart.timeScale().timeToCoordinate(cb.time);
            const y = candleSeries.priceToCoordinate(cb.price);
            if (x !== null && y !== null && x >= 75 && x <= rightX - 10 && y >= 10 && y <= h - 20) {{
                // Gold/Ochre (#B45309) for absorption, Dark Blue (#1D4ED8) for Delta
                ctx.fillStyle = cb.isGold ? '#B45309' : '#1D4ED8';
                ctx.beginPath();
                ctx.arc(x, y, 8.5, 0, Math.PI * 2);
                ctx.fill();
                ctx.strokeStyle = cb.isGold ? '#FDE047' : '#93C5FD';
                ctx.lineWidth = 0.8;
                ctx.stroke();

                ctx.fillStyle = '#FFFFFF';
                ctx.font = 'bold 8.5px "JetBrains Mono", monospace';
                ctx.textAlign = 'center';
                ctx.fillText(cb.vol, x, y + 3);
            }}
        }});
    }}
}}

// ----------------------------------------------------------------------------
// Realtime Tick Feeder & In-Browser Dynamic Greeks Recalculation
// ----------------------------------------------------------------------------
function onTick(price, isUserOverride = false) {{
    const prevPrice = currentPrice;
    currentPrice = price;

    const res = Black76Engine.recalculate(currentPrice, window.INITIAL_OPTIONS, window.INITIAL_META);

    const elTickerPrice = document.getElementById('top-ticker-price');
    const elTickerChange = document.getElementById('top-ticker-change');
    const diff = currentPrice - initialBasePrice;
    const pct = (diff / initialBasePrice) * 100.0;

    if (elTickerPrice) {{
        elTickerPrice.innerText = currentPrice.toLocaleString('en-US', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }});
        elTickerPrice.style.color = currentPrice >= prevPrice ? '#4ADE80' : '#F87171';
    }}
    if (elTickerChange) {{
        elTickerChange.innerText = (diff >= 0 ? "+" : "") + diff.toFixed(2) + " (" + (diff >= 0 ? "+" : "") + pct.toFixed(2) + "%)";
        elTickerChange.className = 'ticker-change ' + (diff >= 0 ? 'change-up' : 'change-down');
    }}
    const elAtm = document.getElementById('top-ticker-atm');
    if (elAtm) elAtm.innerText = res.atmStrike.toLocaleString() + " pts";
    const elIv = document.getElementById('top-ticker-iv');
    if (elIv) elIv.innerText = (res.atmIV * 100).toFixed(1) + "%";

    const elSpotNum = document.getElementById('kpi-spot-num');
    if (elSpotNum) elSpotNum.innerText = currentPrice.toLocaleString('en-US', {{ minimumFractionDigits: 1, maximumFractionDigits: 1 }});

    const elMt5Num = document.getElementById('kpi-mt5-num');
    if (elMt5Num) {{
        const mt5P = currentPrice - window.INITIAL_META.basis;
        elMt5Num.innerText = mt5P.toLocaleString('en-US', {{ minimumFractionDigits: 1, maximumFractionDigits: 1 }});
    }}

    const elGexVal = document.getElementById('kpi-gex-val');
    if (elGexVal) {{
        elGexVal.innerText = (res.totalGEX >= 0 ? "+" : "") + "$" + res.totalGEX.toFixed(1) + "M GEX";
        elGexVal.style.color = res.totalGEX >= 0 ? '#4ADE80' : '#F87171';
    }}

    const elRegimeBadge = document.getElementById('regime-badge');
    if (elRegimeBadge) {{
        if (res.totalGEX >= 5.0) {{
            elRegimeBadge.className = 'badge badge-pos';
            elRegimeBadge.innerText = 'POSITIVE GAMMA (NÉN BIẾN ĐỘ / FADE)';
        }} else if (res.totalGEX <= -5.0) {{
            elRegimeBadge.className = 'badge badge-neg';
            elRegimeBadge.innerText = 'NEGATIVE GAMMA (KHUẾCH ĐẠI / BREAKOUT)';
        }} else {{
            elRegimeBadge.className = 'badge badge-gold';
            elRegimeBadge.innerText = 'NEUTRAL TRANSITION (CÂN BẰNG)';
        }}
    }}

    const elMoveVal = document.getElementById('kpi-move-val');
    if (elMoveVal) elMoveVal.innerText = "±" + res.expectedMove.toFixed(1) + " pts";

    const elVexVal = document.getElementById('kpi-vex-val');
    if (elVexVal) {{
        elVexVal.innerText = (res.totalVEX >= 0 ? "+" : "") + "$" + res.totalVEX.toFixed(1) + "M / " + (res.totalCHEX >= 0 ? "+" : "") + "$" + res.totalCHEX.toFixed(1) + "M";
    }}

    // Recalculate F0 Theoretical & Delta F Spread
    const divYield = window.INITIAL_META.div_yield || 0.0058;
    const spotUnd = window.INITIAL_META.spot_underlying || (currentPrice - 12.5);
    const f0Fair = spotUnd * Math.exp((rRate - divYield) * tYears);
    const deltaF = currentPrice - f0Fair;

    const f0FairEl = document.getElementById("top-ticker-f0-fair");
    if (f0FairEl) f0FairEl.textContent = f0Fair.toLocaleString('en-US', {{ minimumFractionDigits: 1, maximumFractionDigits: 1 }});
    const deltaFEl = document.getElementById("top-ticker-delta-f");
    if (deltaFEl) {{
        const statusText = deltaF > 3 ? "PREMIUM • MUA ĐUỔI" : (deltaF < -3 ? "DISCOUNT • BÁN XẢ" : "FAIR VALUE • CÂN BẰNG");
        const badgeCls = deltaF > 3 ? "badge badge-pos" : (deltaF < -3 ? "badge badge-neg" : "badge badge-gold");
        deltaFEl.className = badgeCls;
        deltaFEl.innerHTML = (deltaF >= 0 ? "+" : "") + deltaF.toFixed(1) + " pts (" + statusText + ")";
    }}
    const kpiFairEl = document.getElementById("kpi-fair-f0");
    if (kpiFairEl) kpiFairEl.textContent = f0Fair.toLocaleString('en-US', {{ minimumFractionDigits: 1, maximumFractionDigits: 1 }});
    const kpiDeltaEl = document.getElementById("kpi-delta-f");
    if (kpiDeltaEl) {{
        kpiDeltaEl.style.color = deltaF > 3 ? "#4ADE80" : (deltaF < -3 ? "#F87171" : "#FACC15");
        kpiDeltaEl.textContent = (deltaF >= 0 ? "+" : "") + deltaF.toFixed(1) + " pts";
    }}
    const kpiDeltaStatEl = document.getElementById("kpi-delta-status");
    if (kpiDeltaStatEl) {{
        kpiDeltaStatEl.textContent = deltaF > 3 ? "PREMIUM • MUA ĐUỔI" : (deltaF < -3 ? "DISCOUNT • BÁN XẢ" : "FAIR VALUE • CÂN BẰNG");
    }}

    const setHud = (id, v, unit, pos, neg) => {{
        const el = document.getElementById(id);
        if (!el) return;
        el.innerText = (v >= 0 ? '+$' : '-$') + Math.abs(v).toFixed(1) + unit;
        if (pos) el.style.color = v >= 0 ? pos : neg;
    }};
    setHud('hud-gex-val', res.totalGEX, 'M', '#4ADE80', '#F87171');
    setHud('hud-vanna-val', res.totalVEX, 'M');
    setHud('hud-charm-val', res.totalCHEX, 'M/d');
    setHud('hud-theta-val', res.totalTEX, 'M/d');

    // Update top bar stats
    const topGex = document.getElementById('kpi-gex-val');
    if (topGex) {{
        topGex.innerText = (res.totalGEX >= 0 ? '+$' : '-$') + Math.abs(res.totalGEX).toFixed(1) + 'M';
        topGex.style.color = res.totalGEX >= 0 ? '#4ADE80' : '#F87171';
    }}
    const topCharm = document.getElementById('top-charm-val');
    if (topCharm) topCharm.innerText = (res.totalCHEX >= 0 ? '+$' : '-$') + Math.abs(res.totalCHEX).toFixed(1) + 'M/d';
    const topVex = document.getElementById('kpi-vex-val');
    if (topVex) topVex.innerText = (res.totalVEX >= 0 ? '+$' : '-$') + Math.abs(res.totalVEX).toFixed(1) + 'M';
    const topTex = document.getElementById('top-theta-val');
    if (topTex) topTex.innerText = (res.totalTEX >= 0 ? '+$' : '-$') + Math.abs(res.totalTEX).toFixed(1) + 'M/d';

    drawAtasOverlay();

    const elRadar = document.getElementById('live-greeks-radar');
    if (elRadar && res.atmGreeks) {{
        const g = res.atmGreeks;
        elRadar.innerHTML = "Delta &Delta;: <b>" + g.delta.toFixed(3) + "</b> | Gamma &Gamma;: <b>" + g.gamma.toFixed(5) + "</b> | Vega &nu;: <b>$" + g.vega.toFixed(1) + "M</b> | Theta &theta;: <b>" + g.theta.toFixed(1) + "k/d</b> | Vanna (VEX): <b>" + (g.vanna >= 0 ? "+" : "") + "$" + g.vanna.toFixed(1) + "M</b> | Charm (CHEX): <b>" + (g.charm >= 0 ? "+" : "") + "$" + g.charm.toFixed(1) + "M/d</b>";
    }}

    if (candleSeries && livePriceLine) {{
        livePriceLine.applyOptions({{ price: currentPrice }});

        const nowSec = Math.floor(Date.now() / 1000);
        const barTime = nowSec - (nowSec % currentPeriod);

        if (!lastCandle || barTime > lastCandle.time) {{
            lastCandle = {{
                time: barTime,
                open: currentPrice,
                high: currentPrice,
                low: currentPrice,
                close: currentPrice
            }};
        }} else {{
            lastCandle.high = Math.max(lastCandle.high, currentPrice);
            lastCandle.low = Math.min(lastCandle.low, currentPrice);
            lastCandle.close = currentPrice;
        }}
        candleSeries.update(lastCandle);
        drawAtasOverlay();
    }}

    const strikes = window.INITIAL_OPTIONS;
    strikes.forEach(s => {{
        const rowEl = document.getElementById("row-strike-" + Math.round(s.strike));
        const isNear = Math.abs(s.strike - currentPrice) <= (window.INITIAL_META.step * 0.5);
        if (rowEl) {{
            if (isNear) {{
                rowEl.className = 'row-spot';
            }} else {{
                rowEl.className = '';
            }}
        }}
        const cellGex = document.getElementById("cell-gex-" + Math.round(s.strike));
        if (cellGex && s.currentNetGEX !== undefined) {{
            cellGex.innerText = (s.currentNetGEX >= 0 ? "+" : "") + "$" + s.currentNetGEX.toFixed(2) + "M";
            cellGex.style.color = s.currentNetGEX >= 0 ? '#4ADE80' : '#F87171';
        }}
    }});
}}

// Clean Pure ATAS: Always anchored to official CME Globex settlement price
function startSimulation() {{
    // Zero-Waste: No dummy simulation intervals
}}

function setTimeframe(tf) {{
    currentTimeframe = tf.toLowerCase();
    const periodMap = {{
        '1m': 60,
        '5m': 300,
        '15m': 900,
        '1h': 3600,
        'd': 86400
    }};
    const period = periodMap[currentTimeframe] || 60;

    document.querySelectorAll('.timeframe-pill').forEach(btn => {{
        if (btn.innerText.toLowerCase() === currentTimeframe) {{
            btn.classList.add('active');
        }} else {{
            btn.classList.remove('active');
        }}
    }});

    if (candleSeries) {{
        buildHistoricalBars(period);
    }}
}}

document.addEventListener('DOMContentLoaded', () => {{
    initAtasChart();
    if (window.INITIAL_META && window.INITIAL_META.spot) {{
        onTick(window.INITIAL_META.spot);
    }}
    startSimulation();
}});
</script>
</body>
</html>
"""
    return html


def build_and_export_dashboard(
    csv_path: Optional[str] = "data/options_prices_NQZ26.csv",
    output_paths: Optional[List[str]] = None,
    basis: float = 0.0,
    multiplier: float = 20.0,
    source: str = "yfinance",
    spot: Optional[float] = None,
) -> str:
    """Build complete Plotly terminal and export to output HTML file paths."""
    if output_paths is None or len(output_paths) == 0:
        output_paths = ["exports/latest_nq_dashboard.html", "exports/index.html"]

    df_full, meta = load_options_dataset(
        csv_path=csv_path,
        basis=basis,
        multiplier=multiplier,
        source=source,
        spot_override=spot,
    )
    fig = build_plotly_terminal(df_full, meta)
    html_content = generate_html_terminal(df_full, meta, fig)

    for out_p in output_paths:
        p = Path(out_p)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"[+] [Dashboard] Exported standalone terminal to: {p} ({p.stat().st_size:,} bytes)")

    json_path = Path("exports/nq_tactical_levels.json")
    try:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_feed = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "symbol": "QQQ" if source == "yfinance" else "NQ",
            "futures_symbol": "NQ=F",
            "source": source,
            "metrics": meta,
        }
        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(json_feed, jf, indent=2, default=str)
        print(f"[+] [Dashboard] Exported hot tactical JSON to: {json_path}")
    except Exception as e:
        print(f"[!] Warning: Could not export JSON feed: {e}")

    return output_paths[0]


def main():
    parser = argparse.ArgumentParser(description="Neiro-NQ-Quant Tactical HTML Dashboard Generator")
    parser.add_argument("--source", default="yfinance", choices=["yfinance", "barchart", "csv"], help="Options data source (yfinance is fast, free, no browser)")
    parser.add_argument("--input", default="data/options_prices_NQZ26.csv", help="Input options CSV dataset (if using csv/barchart)")
    parser.add_argument("--output", nargs="+", default=["exports/latest_nq_dashboard.html", "exports/index.html"], help="Output HTML file path(s)")
    parser.add_argument("--basis", type=float, default=0.0, help="MT5 Spot Basis offset (Spot_MT5 = Spot_Futures - basis)")
    parser.add_argument("--spot", type=float, default=None, help="Explicit market futures price override (e.g. 28543.0 for exact CME Globex or 28525.0 for MT5)")
    parser.add_argument("--multiplier", type=float, default=20.0, help="Options multiplier (20 for NQ, 2 for MNQ)")
    args = parser.parse_args()

    build_and_export_dashboard(
        csv_path=args.input,
        output_paths=args.output,
        basis=args.basis,
        multiplier=args.multiplier,
        source=args.source,
        spot=args.spot,
    )


if __name__ == "__main__":
    main()
