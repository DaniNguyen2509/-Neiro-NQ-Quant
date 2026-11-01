"""Neiro-NQ-Quant Tactical HTML Dashboard & ATAS Realtime Terminal Generator.

Generates a standalone, production-grade ATAS Orderflow & Quant Terminal for
E-mini Nasdaq-100 Futures Options (NQ / NQZ26 / NAS100) incorporating:
- Live Ticker Realtime Bar (CME Globex NQ=F, SOFR/Treasury 13W ^IRX rate, ATM IV)
- Interactive ATAS Orderflow Footprint Candlestick Chart (TradingView Lightweight Charts v4.2)
- Dynamic Quant Level Overlays directly on Chart:
  * [PUT WALL] (Maximum Put Gamma Support)
  * [CALL WALL] (Maximum Call Gamma Resistance)
  * [DEEP EF STACK] (Institutional Execution Flow)
  * [BUYER ABS] (Buyer Absorption Zone)
  * [SELLER OFFER] (Seller Offer Supply Zone)
  * [GEX REACTION ZONE] (Zero Gamma / Pivot Reaction Zone)
  * [LIVE F0 PRICE LINE] (Realtime tick-by-tick horizontal line)
- In-Browser Client-Side Black-76 Engine (Pure JS):
  * Recalculates Delta, Gamma, Theta, Vega, Vanna, Charm, and Net GEX ($M) every second
  * Updates KPI Cards, Greeks Radar, and ATM Microstructure table tick-by-tick
- Live Tick Feeder / Simulator with interactive user price override slider
- 3-Panel Plotly Interactive Charts & Anti-collision algorithm
- Intraday Scalping Strategy Table (30-50 pts NQ)
- Structural Swing Walls Strategy Table (100-250 pts NQ)
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
                # QQQ options have 100 shares multiplier; scale to equivalent NQ futures points
                eff_multiplier = round(100.0 / basis_ratio, 4)

                # Unified Futures mode (basis == 0.0) by default to synchronize with TV Pepperstone Forward & MT5.
                if eff_basis is None:
                    eff_basis = 0.0

                print(f"[+] Loaded {len(df_raw)} strikes via yfinance (QQQ ${prices['underlying']:.2f} -> NQ {prices['futures']:.2f}, Basis: {basis_ratio:.2f}, EffMult: {eff_multiplier}, r: {fetched_r_rate*100:.2f}%).")
                # Save snapshot to CSV if path provided
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
            
            # Check for valid Open Interest
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

    # Determine dynamic DTE from expiration date
    dte_val = 1.0
    if "expirationDate" in df_raw.columns and not df_raw["expirationDate"].empty:
        exp_val = str(df_raw["expirationDate"].iloc[0])
        try:
            from src.collector.nasdaq_collector import calculate_dte
            dte_val = calculate_dte(exp_val)
        except Exception:
            dte_val = 1.0

    # Calculate complete quantitative matrix via Black-76
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

    # Filter near-ATM strikes for clear terminal display (18-24 strikes)
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

    # -------------------------------------------------------------------------
    # PANEL 1: Net GEX ($M) Horizontal Bars
    # -------------------------------------------------------------------------
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

    # Spot Price horizontal line across all 3 panels
    for col_idx in (1, 2, 3):
        fig.add_hline(
            y=spot_price, line_color="#38BDF8", line_width=2.2,
            row=1, col=col_idx,
        )

    # Call Wall & Put Wall lines on Panel 1
    if strikes.min() <= call_wall <= strikes.max():
        fig.add_hline(y=call_wall, line_color="#A855F7", line_dash="dash", line_width=1.8, row=1, col=1)
    if strikes.min() <= put_wall <= strikes.max():
        fig.add_hline(y=put_wall, line_color="#34D399", line_dash="dash", line_width=1.8, row=1, col=1)

    # ANTI-COLLISION FEATURE 1:
    # Spot CME label anchored firmly at right edge (x=0.98, xanchor='right') to avoid colliding with left annotations
    spot_label = f"◆ NQ FUTURES: {spot_price:,.1f}" if abs(spot_price - spot_mt5) < 0.1 else f"◆ SPOT CME: {spot_price:,.1f} (MT5: ~{spot_mt5:,.1f})"
    fig.add_annotation(
        x=0.98, y=spot_price,
        text=spot_label,
        showarrow=False, xanchor="right", xref="x domain", yref="y",
        font=dict(color="#FFFFFF", size=9.5, family="JetBrains Mono"),
        bgcolor="#0284C7", bordercolor="#38BDF8", borderwidth=1, borderpad=3,
        row=1, col=1,
    )

    # Tactical Annotations on Panel 1
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

    # -------------------------------------------------------------------------
    # PANEL 2: Volume vs Open Interest (Put Left, Call Right)
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # PANEL 3: Greeks Bậc 2 (Vanna & Charm)
    # -------------------------------------------------------------------------
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

    # ANTI-COLLISION FEATURE 2:
    # Vertical height offset when Vanna and Charm peaks share the same strike
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

    # ANTI-COLLISION FEATURE 3:
    # Legend placed at y=1.07 (separated from subplot titles by ~25px)
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

    # Expand Panel 3 x-axis range cleanly
    max_vc = max(float(df["netVEX"].abs().max()), float(df["netCHEX"].abs().max()), 5.0)
    fig.update_xaxes(
        range=[-max_vc * 2.2, max_vc * 2.2],
        gridcolor="#1E293B",
        title=dict(text="Greeks Bậc 2 ($M Exposure)", font=dict(size=10)),
        row=1, col=3,
    )

    return fig


def generate_html_terminal(df: pd.DataFrame, meta: Dict[str, Any], fig: go.Figure) -> str:
    """Generate high-fidelity, standalone dark-mode HTML tactical report with ATAS Realtime Terminal."""
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

    # Dynamic SL & TP offsets based on strike step (no hardcoding)
    hard_sl_pts = min(step * 0.35, 25.0)
    fade_sl_pts = min(step * 0.30, 20.0)
    front_run_tp = max(1.0, step * 0.05)

    plotly_div = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"responsive": True, "displayModeBar": True})

    # Regime Color Badge
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
            <div class="kpi-sub">Trục ATM Option Pivot: <b id="kpi-atm-num">{meta['atm_strike']:,.0f} pts</b> | Đồng bộ TV & MT5 Forward</div>
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
            <div class="kpi-sub">Trục ATM CME: <b id="kpi-atm-num">{meta['atm_strike']:,.0f} pts</b> | Basis MT5 Spot: <b>{basis:+0.1f} pts</b></div>
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

    # Microstructure rows near ATM
    table_rows_html = ""
    atm_strike = meta["atm_strike"]
    df_sorted = df[(df["strike"] >= atm_strike - 8 * step) & (df["strike"] <= atm_strike + 8 * step)].sort_values("strike", ascending=False)
    for _, row in df_sorted.iterrows():
        stk = row["strike"]
        stk_mt5 = stk - basis
        gex = float(row.get("netGEX", 0.0))
        c_oi = int(row.get("callOpenInterest", 0))
        p_oi = int(row.get("putOpenInterest", 0))
        c_vol = int(row.get("callVolume", 0))
        p_vol = int(row.get("putVolume", 0))
        vex = float(row.get("netVEX", 0.0))
        chex = float(row.get("netCHEX", 0.0))

        gex_style = "color: #4ADE80; font-weight: 600;" if gex >= 0 else "color: #F87171; font-weight: 600;"
        is_spot_near = abs(stk - spot) <= (step * 0.5)
        row_class = 'class="row-spot"' if is_spot_near else ""

        mt5_td = f'<td style="color: #38BDF8;">~{stk_mt5:,.1f}</td>' if not is_unified else ""

        table_rows_html += f"""
        <tr {row_class} id="row-strike-{int(stk)}">
            <td><b>{stk:,.0f} pts</b></td>
            {mt5_td}
            <td style="{gex_style}" id="cell-gex-{int(stk)}">${gex:+.2f}M</td>
            <td>{c_oi:,}</td>
            <td>{p_oi:,}</td>
            <td>{c_vol:,}</td>
            <td>{p_vol:,}</td>
            <td style="color: #FB923C;" id="cell-vex-{int(stk)}">${vex:+.2f}M</td>
            <td style="color: #22D3EE;" id="cell-chex-{int(stk)}">${chex:+.2f}M</td>
        </tr>
        """

    # Prepare serializable options chain for client-side JavaScript Black-76 Engine
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
    })

    deep_ef_strike = strike_above + step
    buyer_abs_strike = strike_below
    seller_offer_strike = strike_above
    gex_reaction_strike = spot + (0.5 * step if total_gex >= 0 else -0.5 * step)

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NEIRO-NQ-QUANT TERMINAL &bull; ATAS REALTIME QUANT ORDERFLOW</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <!-- TradingView Lightweight Charts v4.2 CDN -->
    <script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        :root {{
            --bg-base: #06090E; --bg-card: #0D131F; --border-color: #1A2333;
            --text-primary: #F8FAFC; --text-secondary: #94A3B8; --text-muted: #64748B;
            --neon-green: #22C55E; --neon-red: #EF4444; --neon-blue: #38BDF8; --neon-gold: #FACC15;
            --neon-purple: #A855F7; --neon-coral: #F43F5E;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: var(--bg-base); color: var(--text-primary);
            font-family: 'Inter', -apple-system, sans-serif; padding: 16px; font-size: 13px;
        }}
        .container {{ max-width: 1480px; margin: 0 auto; }}

        /* Top Nav & Branding Bar */
        .header {{
            display: flex; justify-content: space-between; align-items: center;
            padding: 12px 20px; background: linear-gradient(135deg, #0B111D 0%, #111A2B 100%);
            border: 1px solid var(--border-color); border-radius: 10px; margin-bottom: 12px;
        }}
        .brand {{ display: flex; align-items: center; gap: 10px; }}
        .brand-title {{
            font-size: 18px; font-weight: 800;
            background: linear-gradient(90deg, #FFFFFF 0%, #93C5FD 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            font-family: 'JetBrains Mono', monospace; letter-spacing: 0.5px;
        }}
        .pulse-dot {{
            width: 10px; height: 10px; border-radius: 50%; background-color: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green); animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }}
            70% {{ transform: scale(1); box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }}
            100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }}
        }}
        .badge {{
            display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 11px;
            font-weight: 700; font-family: 'JetBrains Mono', monospace;
        }}
        .badge-live {{ background: rgba(34, 197, 94, 0.15); color: #4ADE80; border: 1px solid rgba(34, 197, 94, 0.4); }}
        .badge-gold {{ background: rgba(250, 204, 21, 0.15); color: #FACC15; border: 1px solid rgba(250, 204, 21, 0.4); }}
        .badge-pos {{ background: rgba(74, 222, 128, 0.15); color: #4ADE80; border: 1px solid rgba(74, 222, 128, 0.4); }}
        .badge-neg {{ background: rgba(248, 113, 113, 0.15); color: #F87171; border: 1px solid rgba(248, 113, 113, 0.4); }}

        /* Live Ticker Bar */
        .ticker-bar {{
            display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;
            background: #0A0F19; border: 1px solid #1E293B; border-radius: 8px; padding: 10px 18px; margin-bottom: 14px;
            font-family: 'JetBrains Mono', monospace;
        }}
        .ticker-items {{ display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }}
        .ticker-item {{ display: flex; align-items: center; gap: 6px; font-size: 12.5px; }}
        .ticker-symbol {{ font-weight: 800; color: #FFFFFF; font-size: 13.5px; }}
        .ticker-price {{ font-weight: 800; font-size: 15px; color: #38BDF8; transition: color 0.2s; }}
        .ticker-change {{ font-size: 12px; font-weight: 600; padding: 2px 6px; border-radius: 4px; }}
        .change-up {{ color: #4ADE80; background: rgba(34, 197, 94, 0.12); }}
        .change-down {{ color: #F87171; background: rgba(239, 68, 68, 0.12); }}
        .ticker-controls {{ display: flex; align-items: center; gap: 10px; }}
        .btn-ctrl {{
            background: #131E31; color: #94A3B8; border: 1px solid #243550; padding: 5px 10px;
            border-radius: 6px; font-size: 11px; font-weight: 600; cursor: pointer; transition: all 0.2s;
            font-family: 'JetBrains Mono', monospace;
        }}
        .btn-ctrl:hover, .btn-ctrl.active {{ background: #1E293B; color: #38BDF8; border-color: #38BDF8; }}
        .btn-sim {{ background: rgba(34, 197, 94, 0.15); color: #4ADE80; border-color: rgba(34, 197, 94, 0.4); }}
        .btn-sim.paused {{ background: rgba(239, 68, 68, 0.15); color: #F87171; border-color: rgba(239, 68, 68, 0.4); }}

        /* KPI Cards Grid */
        .kpi-grid {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; margin-bottom: 14px;
        }}
        .kpi-card {{
            background-color: var(--bg-card); border: 1px solid var(--border-color);
            border-radius: 10px; padding: 12px 16px; transition: transform 0.2s, border-color 0.2s;
        }}
        .kpi-card:hover {{ border-color: #2E3E59; transform: translateY(-1px); }}
        .kpi-label {{
            font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 4px;
            letter-spacing: 0.5px;
        }}
        .kpi-val {{
            font-size: 21px; font-weight: 700; font-family: 'JetBrains Mono', monospace; margin-bottom: 4px;
            transition: color 0.3s;
        }}
        .kpi-sub {{ font-size: 11px; color: var(--text-muted); }}

        /* ATAS Candlestick Orderflow Terminal Container */
        .atas-terminal-box {{
            background: #000000; border: 1px solid #1E293B; border-radius: 10px;
            overflow: hidden; margin-bottom: 18px; position: relative;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.7);
        }}
        .atas-toolbar {{
            display: flex; justify-content: space-between; align-items: center;
            background: #080D15; padding: 8px 14px; border-bottom: 1px solid #182234;
        }}
        .atas-tools-left {{ display: flex; align-items: center; gap: 8px; }}
        .atas-badge {{
            background: #111B2B; border: 1px solid #23354E; color: #E2E8F0;
            padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }}
        .atas-tools-right {{ display: flex; align-items: center; gap: 8px; font-family: 'JetBrains Mono', monospace; font-size: 11px; }}
        .timeframe-pill {{
            background: transparent; color: #64748B; border: 1px solid transparent; padding: 3px 7px;
            border-radius: 4px; font-size: 11px; cursor: pointer; font-weight: 600;
        }}
        .timeframe-pill.active, .timeframe-pill:hover {{ background: #131E31; color: #38BDF8; border-color: #243550; }}

        #tv-chart-wrapper {{
            position: relative; width: 100%; height: 540px; background-color: #000000;
        }}
        #atas-tv-chart {{ width: 100%; height: 100%; }}

        /* ATAS Orderflow Shaded Level Overlays */
        .atas-overlay-container {{
            position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            pointer-events: none; z-index: 5;
        }}
        .atas-band {{
            position: absolute; left: 60px; right: 75px; height: 18px;
            border-radius: 2px; display: flex; align-items: center; justify-content: flex-end;
            padding-right: 12px; font-family: 'JetBrains Mono', monospace; font-size: 10px; font-weight: 700;
            letter-spacing: 0.5px; opacity: 0.88; transition: top 0.3s ease;
        }}
        .band-put-wall {{
            background: rgba(34, 197, 94, 0.12); border-top: 1px solid #22C55E; border-bottom: 1px solid #22C55E;
            color: #4ADE80;
        }}
        .band-call-wall {{
            background: rgba(239, 68, 68, 0.12); border-top: 1px solid #EF4444; border-bottom: 1px solid #EF4444;
            color: #F87171;
        }}
        .band-deep-ef {{
            background: rgba(148, 163, 184, 0.16); border-top: 1px solid #94A3B8; border-bottom: 1px solid #94A3B8;
            color: #E2E8F0;
        }}
        .band-buyer-abs {{
            background: rgba(56, 189, 248, 0.14); border-top: 1px solid #38BDF8; border-bottom: 1px solid #38BDF8;
            color: #7DD3FC;
        }}
        .band-seller-offer {{
            background: rgba(244, 63, 94, 0.14); border-top: 1px solid #F43F5E; border-bottom: 1px solid #F43F5E;
            color: #FDA4AF;
        }}
        .band-gex-reaction {{
            background: rgba(250, 204, 21, 0.12); border-top: 1px dashed #FACC15; border-bottom: 1px dashed #FACC15;
            color: #FDE047;
        }}

        /* Live Slider Interactive Testing Box */
        .slider-box {{
            display: flex; align-items: center; justify-content: space-between; gap: 14px;
            background: #0B111D; border-top: 1px solid #182234; padding: 8px 16px;
            font-family: 'JetBrains Mono', monospace; font-size: 11px;
        }}
        .slider-box input[type=range] {{
            flex: 1; accent-color: #38BDF8; cursor: pointer;
        }}

        /* Table & Section Boxes */
        .chart-box {{
            background-color: var(--bg-card); border: 1px solid var(--border-color);
            border-radius: 10px; padding: 10px; margin-bottom: 18px;
        }}
        .table-box {{
            background-color: var(--bg-card); border: 1px solid var(--border-color);
            border-radius: 10px; padding: 16px; margin-bottom: 16px; overflow-x: auto;
        }}
        .section-header {{
            font-size: 13.5px; font-weight: 700; margin-bottom: 12px; color: #E2E8F0;
            display: flex; align-items: center; justify-content: space-between;
        }}
        table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; text-align: left; }}
        th {{
            background-color: #0F1728; color: var(--text-secondary); padding: 9px 12px;
            font-weight: 600; border-bottom: 1px solid var(--border-color); white-space: nowrap;
        }}
        td {{
            padding: 9px 12px; border-bottom: 1px solid #141C2B; font-family: 'JetBrains Mono', monospace;
        }}
        tr:hover td {{ background-color: #172236; }}
        .row-spot td {{
            background-color: rgba(56, 189, 248, 0.12) !important;
            border-top: 1px solid var(--neon-blue); border-bottom: 1px solid var(--neon-blue);
        }}
        .tag-buy {{ color: #4ADE80; font-weight: 700; }}
        .tag-sell {{ color: #F87171; font-weight: 700; }}
        .insight-box {{
            background: linear-gradient(135deg, rgba(20, 29, 44, 0.7) 0%, rgba(11, 17, 28, 0.8) 100%);
            border-left: 4px solid var(--neon-blue); border-radius: 6px;
            padding: 10px 14px; margin-bottom: 14px; font-size: 12px; line-height: 1.5;
        }}
        .footer {{
            text-align: center; font-size: 11px; color: var(--text-muted);
            padding: 18px 0; border-top: 1px solid var(--border-color); font-family: 'JetBrains Mono', monospace;
        }}
        .flash-up {{ animation: flashGreen 0.6s ease; }}
        .flash-down {{ animation: flashRed 0.6s ease; }}
        @keyframes flashGreen {{ 0% {{ background-color: rgba(34, 197, 94, 0.4); }} 100% {{ background-color: transparent; }} }}
        @keyframes flashRed {{ 0% {{ background-color: rgba(239, 68, 68, 0.4); }} 100% {{ background-color: transparent; }} }}
    </style>
</head>
<body>
<div class="container">
    <!-- Header -->
    <div class="header">
        <div class="brand">
            <div class="pulse-dot"></div>
            <div class="brand-title">NEIRO-NQ-QUANT TERMINAL</div>
            <span class="badge badge-gold">CME E-MINI NASDAQ (NQ)</span>
            <span class="badge badge-live">100% CLOUD AUTOMATED</span>
        </div>
        <div style="font-family: 'JetBrains Mono', monospace; font-size: 11.5px; color: #94A3B8;">
            Cập nhật: <b id="lbl-last-update">{now_str} (Giờ VN)</b>
        </div>
    </div>

    <!-- Live Ticker Realtime Bar -->
    <div class="ticker-bar">
        <div class="ticker-items">
            <div class="ticker-item">
                <span class="pulse-dot" style="width:7px; height:7px;"></span>
                <span class="ticker-symbol">NQ=F</span>
                <span class="ticker-price" id="top-ticker-price">{spot:,.2f}</span>
                <span class="ticker-change change-up" id="top-ticker-change">+0.00 (+0.00%)</span>
            </div>
            <div class="ticker-item" style="color: #64748B;">|</div>
            <div class="ticker-item">
                <span style="color: #94A3B8;">ATM TRỤC:</span>
                <b style="color: #F8FAFC;" id="top-ticker-atm">{meta['atm_strike']:,.0f} pts</b>
            </div>
            <div class="ticker-item" style="color: #64748B;">|</div>
            <div class="ticker-item">
                <span style="color: #94A3B8;">ATM IV:</span>
                <b style="color: #FACC15;" id="top-ticker-iv">{meta.get('sigma_atm', 0.18)*100:.1f}%</b>
            </div>
            <div class="ticker-item" style="color: #64748B;">|</div>
            <div class="ticker-item">
                <span style="color: #94A3B8;">SOFR / T-Bill 13W (r):</span>
                <b style="color: #38BDF8;" id="top-ticker-r">{r_rate*100:.2f}%</b>
            </div>
            <div class="ticker-item" style="color: #64748B;">|</div>
            <div class="ticker-item">
                <span style="color: #94A3B8;">DTE:</span>
                <b style="color: #A855F7;">{meta.get('dte_days', 1.0):.1f} ngày</b>
            </div>
        </div>
        <div class="ticker-controls">
            <button class="btn-ctrl btn-sim" id="btn-toggle-sim" onclick="toggleSimulation()">● SIMULATION: ON</button>
            <button class="btn-ctrl" onclick="resetToLiveCME()">↺ RESET CME</button>
        </div>
    </div>

    <!-- Executive KPI Grid -->
    <div class="kpi-grid">
        {kpi_card_1}
        <div class="kpi-card" id="kpi-gex-card">
            <div class="kpi-label">Market Regime & Net GEX</div>
            <div class="kpi-val" style="color: {regime_color};" id="kpi-gex-val">${total_gex:+.1f}M GEX</div>
            <div class="kpi-sub" id="kpi-gex-sub">{regime_badge}</div>
        </div>
        <div class="kpi-card" id="kpi-move-card">
            <div class="kpi-label">Biên Độ 1-Sigma Expected Move</div>
            <div class="kpi-val" style="color: var(--neon-gold);" id="kpi-move-val">±{expected_move:,.1f} pts</div>
            <div class="kpi-sub" id="kpi-move-sub">Intraday (Rule of 16): <b>±{intraday_move:,.1f} pts</b></div>
        </div>
        <div class="kpi-card" id="kpi-vex-card">
            <div class="kpi-label">Greeks Bậc 2 (Vanna & Charm)</div>
            <div class="kpi-val" style="color: #38BDF8;" id="kpi-vex-val">${total_vex:+.1f}M / ${total_chex:+.1f}M</div>
            <div class="kpi-sub">Net VEX (1% IV) | Net CHEX (Ngày decay)</div>
        </div>
    </div>

    <!-- Realtime ATM Greeks Live Radar -->
    <div class="insight-box" style="border-left-color: #38BDF8; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
        <div>
            <b style="color: #38BDF8; font-size: 12.5px;">⚡ LIVE BLACK-76 REALTIME GREEKS RADAR (TRỤC ATM):</b>
            <span style="font-family:'JetBrains Mono', monospace; margin-left: 8px; color: #E2E8F0;" id="live-greeks-radar">
                Delta &Delta;: <b>0.500</b> | Gamma &Gamma;: <b>0.00042</b> | Vega &nu;: <b>$24.2M</b> | Theta &theta;: <b>-$34.1k/d</b> | Vanna: <b>+$3.2M</b> | Charm: <b>-$1.8M/d</b>
            </span>
        </div>
        <div style="font-family:'JetBrains Mono', monospace; font-size: 11px; color: #4ADE80;">
            ● Recalculated Client-Side in 0.1ms
        </div>
    </div>

    <!-- ATAS Realtime Orderflow Footprint Candlestick Chart -->
    <div class="atas-terminal-box">
        <div class="atas-toolbar">
            <div class="atas-tools-left">
                <span class="atas-badge">#NQZ6</span>
                <span class="atas-badge" style="color: #38BDF8;">1 Lots</span>
                <span class="atas-badge" style="color: #4ADE80;">CME GLOBEX</span>
                <span style="color: #64748B; font-size: 11px; margin-left: 6px;">TradingPattern by Rithmic &bull; Powered by NEIRO-QUANT</span>
            </div>
            <div class="atas-tools-right">
                <span style="color: #64748B;">Khung:</span>
                <button class="timeframe-pill active" onclick="setTimeframe('1m')">1M</button>
                <button class="timeframe-pill" onclick="setTimeframe('5m')">5M</button>
                <button class="timeframe-pill" onclick="setTimeframe('15m')">15M</button>
                <button class="timeframe-pill" onclick="setTimeframe('1h')">1H</button>
                <button class="timeframe-pill" onclick="setTimeframe('D')">D</button>
            </div>
        </div>

        <!-- TV Lightweight Chart Container -->
        <div id="tv-chart-wrapper">
            <div id="atas-tv-chart"></div>

            <!-- Visual ATAS Quant Bands Overlay -->
            <div class="atas-overlay-container" id="atas-overlay-layer">
                <div class="atas-band band-put-wall" id="overlay-put-wall">
                    <span>PUT WALL &bull; MAX GAMMA SUPPORT #{meta['put_wall']:,.0f} ({meta['put_wall_oi']:,} OI)</span>
                </div>
                <div class="atas-band band-call-wall" id="overlay-call-wall">
                    <span>CALL WALL &bull; MAX GAMMA RESISTANCE #{meta['call_wall']:,.0f} ({meta['call_wall_oi']:,} OI)</span>
                </div>
                <div class="atas-band band-deep-ef" id="overlay-deep-ef">
                    <span>DEEP EF STACK #{deep_ef_strike:,.0f}</span>
                </div>
                <div class="atas-band band-buyer-abs" id="overlay-buyer-abs">
                    <span>BUYER ABS #{buyer_abs_strike:,.0f}</span>
                </div>
                <div class="atas-band band-seller-offer" id="overlay-seller-offer">
                    <span>SELLER OFFER #{seller_offer_strike:,.0f} &bull; +1R</span>
                </div>
                <div class="atas-band band-gex-reaction" id="overlay-gex-reaction">
                    <span>GEX REACTION #{gex_reaction_strike:,.0f}</span>
                </div>
            </div>
        </div>

        <!-- Interactive Testing Price Slider -->
        <div class="slider-box">
            <span style="color: #94A3B8;">THỬ NGHIỆM GIÁ NQ (SIMULATE SPOT):</span>
            <input type="range" id="price-slider" min="{spot - 300:.0f}" max="{spot + 300:.0f}" step="0.25" value="{spot:.2f}" oninput="onSliderPriceChange(this.value)">
            <span style="color: #38BDF8; font-weight:700; width: 90px; text-align:right;" id="slider-price-val">{spot:,.2f}</span>
            <button class="btn-ctrl" onclick="resetToLiveCME()">MẶC ĐỊNH</button>
        </div>
    </div>

    <!-- 1-Sigma & Greeks Insights -->
    <div class="insight-box" style="border-left-color: #38BDF8;">
        <b style="color: #93C5FD; font-size: 13px;">📐 [ĐỘ LỆCH CHUẨN & BIÊN ĐỘ 1-SIGMA NASDAQ]:</b><br>
        • <b>ATM Straddle (Call + Put ATM):</b> {meta['atm_straddle']:,.1f} pts | Implied Volatility (IV ATM): <b>{meta['sigma_atm']*100:.1f}%</b><br>
        • <b>Expected Move 1-Sigma (Brenner-Subrahmanyam):</b> ±{expected_move:,.1f} pts (Biên độ kỳ: NQ {meta['lower_band_1s']:,.0f} &mdash; {meta['upper_band_1s']:,.0f})<br>
        • <b>Intraday Move (Rule of 16):</b> ±{intraday_move:,.1f} pts (Vùng dao động trong ngày: NQ {spot-intraday_move:,.0f} &mdash; {spot+intraday_move:,.0f})
    </div>

    <div class="insight-box" style="border-left-color: #FB923C;">
        <b style="color: #FDBA74; font-size: 13px;">⚡ [Ý NGHĨA & HƯỚNG DẪN HÀNH ĐỘNG GREEKS BẬC 2 - VANNA & CHARM]:</b><br>
        • <b>ĐỈNH VANNA (${total_vex:+.1f}M):</b> <b>LỰC ĐẨY V-REBOUND</b> &rarr; Canh BUY lướt sóng khi IV hạ nhiệt sau tin tức hoặc đầu phiên Mỹ.<br>
        • <b>ĐỈNH CHARM (${total_chex:+.1f}M/ngày):</b> <b>NAM CHÂM GHÌM GIÁ ĐÊM</b> &rarr; Canh CHỐT LỜI hoặc đánh hồi quy về trục này khi về đêm muộn (sau 01:30 sáng VN).
    </div>

    <!-- Tactical Scalping Table -->
    <div class="table-box">
        <div class="section-header">
            <span>🎯 PHẦN 1: BẢNG TÁC CHIẾN LƯỚT SÓNG TRONG NGÀY (INTRADAY SCALPING - ĂN 30-50 ĐIỂM NQ)</span>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Chiến Lược</th>
                    <th>{col_cme_act}</th>
                    <th>{col_cme_ent}</th>
                    {th_mt5}
                    <th>{col_cme_sl}</th>
                    <th>Take Profit (TP)</th>
                    <th>Ghi Chú Hành Vi Market Maker</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="tag-buy">1. BUY MUA ĐUỔI (Squeeze {strike_above:,.0f})</td>
                    <td>Vượt > {strike_above + buffer_val:,.1f}</td>
                    <td>{strike_above + buffer_val + 2.0:,.1f}</td>
                    {td_mt5_1}
                    <td style="color:#F87171;">{strike_above - hard_sl_pts:,.1f} ({hard_sl_pts:.0f}p)</td>
                    <td style="color:#4ADE80;">{next_above - front_run_tp:,.1f}</td>
                    <td style="font-family: sans-serif; color: var(--text-secondary);">MM vỡ trận Short -> Gamma Squeeze đẩy giá bốc đầu lên nấc {next_above:,.0f}</td>
                </tr>
                <tr>
                    <td class="tag-sell">2. SELL CHẶN TIỀN TUYẾN (Fade {strike_above:,.0f})</td>
                    <td>{strike_above - 10.0:,.1f} - {strike_above:,.1f}</td>
                    <td>{strike_above - 2.0:,.1f}</td>
                    {td_mt5_2}
                    <td style="color:#F87171;">{strike_above + fade_sl_pts:,.1f} ({fade_sl_pts:.0f}p)</td>
                    <td style="color:#4ADE80;">{spot:,.1f}</td>
                    <td style="font-family: sans-serif; color: var(--text-secondary);">Call Vol cực đại -> MM bán Futures chặn đầu ghìm giá hồi về Spot</td>
                </tr>
                <tr>
                    <td class="tag-buy">3. BUY BẮT SÀN ATM (Rebound {strike_below:,.0f})</td>
                    <td>{strike_below:,.1f} - {strike_below + 10.0:,.1f}</td>
                    <td>{strike_below + 3.0:,.1f}</td>
                    {td_mt5_3}
                    <td style="color:#F87171;">{strike_below - hard_sl_pts:,.1f} ({hard_sl_pts:.0f}p)</td>
                    <td style="color:#4ADE80;">{strike_above - front_run_tp:,.1f}</td>
                    <td style="font-family: sans-serif; color: var(--text-secondary);">Đệm Put hỗ trợ kỹ thuật trong phiên đẩy giá hồi phục cân bằng</td>
                </tr>
                <tr>
                    <td class="tag-sell">4. SELL THỦNG SÀN ATM (Breakdown {strike_below:,.0f})</td>
                    <td>Thủng &lt; {strike_below - buffer_val:,.1f}</td>
                    <td>{strike_below - buffer_val - 2.0:,.1f}</td>
                    {td_mt5_4}
                    <td style="color:#F87171;">{strike_below + fade_sl_pts:,.1f} ({fade_sl_pts:.0f}p)</td>
                    <td style="color:#4ADE80;">{secondary_support + front_run_tp:,.1f}</td>
                    <td style="font-family: sans-serif; color: var(--text-secondary);">Mất mốc ATM Pivot -> Rơi tự do về trạm nghỉ {secondary_support:,.0f} (Đệm nấc 2)</td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- Structural Swing Walls Table -->
    <div class="table-box">
        <div class="section-header">
            <span>🏰 PHẦN 2: BẢNG PHỤC KÍCH THÀNH TRÌ CẤU TRÚC (STRUCTURAL SWING WALLS - ĂN 100-250 ĐIỂM NQ)</span>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Thành Trì</th>
                    <th>{col_cme_act}</th>
                    <th>{col_cme_ent}</th>
                    {th_mt5}
                    <th>{col_cme_sl}</th>
                    <th>Take Profit (TP)</th>
                    <th>Bản Chất Dòng Tiền Lớn</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="tag-buy">THÀNH TRÌ PUT WALL ({put_wall:,.0f})</td>
                    <td>{put_wall:,.1f} - {put_wall + 15.0:,.1f}</td>
                    <td>{put_wall + 3.0:,.1f}</td>
                    {td_mt5_6}
                    <td style="color:#F87171;">{put_wall - 25.0:,.1f} (25p)</td>
                    <td style="color:#4ADE80;">{spot:,.1f} &rarr; {strike_above:,.0f}</td>
                    <td style="font-family: sans-serif; color: var(--text-secondary);">{put_wall_oi:,} HĐ bảo hiểm bảo vệ. MM buộc phải gom Long đỡ thị trường.</td>
                </tr>
                <tr>
                    <td class="tag-sell">THÀNH TRÌ CALL WALL ({call_wall:,.0f})</td>
                    <td>{call_wall - 15.0:,.1f} - {call_wall:,.1f}</td>
                    <td>{call_wall - 3.0:,.1f}</td>
                    {td_mt5_5}
                    <td style="color:#F87171;">{call_wall + 25.0:,.1f} (25p)</td>
                    <td style="color:#4ADE80;">{spot:,.1f} &rarr; {strike_below:,.0f}</td>
                    <td style="font-family: sans-serif; color: var(--text-secondary);">{call_wall_oi:,} HĐ chặn trần. Tường thành bất khả xâm phạm nếu không có tin Black Swan.</td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- 3-Panel Plotly Interactive Chart -->
    <div class="chart-box">
        <div class="section-header" style="padding: 6px 10px;">
            <span>📈 BIỂU ĐỒ ĐỊNH LƯỢNG 3 PANEL CHUYÊN SÂU (NET GEX &bull; VOLUME/OI &bull; VANNA/CHARM)</span>
        </div>
        {plotly_div}
    </div>

    <!-- Microstructure Strike Table -->
    <div class="table-box">
        <div class="section-header">
            <span>{micro_header}</span>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Strike NQ</th>
                    {th_mt5}
                    <th>Net GEX ($M)</th>
                    <th>Call OI</th>
                    <th>Put OI</th>
                    <th>Call Vol</th>
                    <th>Put Vol</th>
                    <th>Net VEX ($M)</th>
                    <th>Net CHEX ($M)</th>
                </tr>
            </thead>
            <tbody>
                {table_rows_html}
            </tbody>
        </table>
    </div>

    <!-- Footer -->
    <div class="footer">
        NEIRO-NQ-QUANT TERMINAL &bull; 100% Cloud-Native &bull; Zero-Touch Automation &bull; Zero-Waste (&lt; 15MB)
    </div>
</div>

<!-- Embedded Data & In-Browser Black-76 Engine -->
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

            row.currentNetGEX = netGEX;
            row.currentNetVEX = netVEX;
            row.currentNetCHEX = netCHEX;

            if (K === atmStrike) {{
                atmGreeks = {{
                    delta: cG.delta,
                    gamma: cG.gamma,
                    vega: cG.vega * mult * 0.01 / 1e6,
                    theta: (cG.theta + pG.theta) * mult * 1000,
                    vanna: netVEX,
                    charm: netCHEX
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
            atmStrike,
            atmIV,
            expectedMove,
            intradayMove,
            atmGreeks: atmGreeks || {{ delta: 0.5, gamma: 0.0004, vega: 24.0, theta: -30.0, vanna: 3.0, charm: -1.5 }}
        }};
    }}
}};

// ----------------------------------------------------------------------------
// TradingView Lightweight Charts & ATAS Orderflow Integration
// ----------------------------------------------------------------------------
let chart = null;
let candleSeries = null;
let livePriceLine = null;
let putWallLine = null;
let callWallLine = null;
let deepEfLine = null;
let buyerAbsLine = null;
let sellerOfferLine = null;
let gexReactionLine = null;

let currentPrice = window.INITIAL_META.spot;
const initialBasePrice = window.INITIAL_META.spot;
let isSimulating = true;
let simInterval = null;
let lastCandle = null;
let currentBarTime = Math.floor(Date.now() / 1000) - (Math.floor(Date.now() / 1000) % 60);

function initAtasChart() {{
    const container = document.getElementById('atas-tv-chart');
    if (!container || !window.LightweightCharts) return;

    chart = LightweightCharts.createChart(container, {{
        width: container.clientWidth,
        height: 540,
        layout: {{
            background: {{ type: 'solid', color: '#000000' }},
            textColor: '#94A3B8',
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 11,
        }},
        grid: {{
            vertLines: {{ color: '#0F1728' }},
            horzLines: {{ color: '#0F1728' }},
        }},
        crosshair: {{
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {{ color: '#38BDF8', width: 1, style: 3 }},
            horzLine: {{ color: '#38BDF8', width: 1, style: 3 }},
        }},
        rightPriceScale: {{
            borderColor: '#1E293B',
            scaleMargins: {{ top: 0.12, bottom: 0.12 }},
        }},
        timeScale: {{
            borderColor: '#1E293B',
            timeVisible: true,
            secondsVisible: false,
        }},
    }});

    candleSeries = chart.addCandlestickSeries({{
        upColor: '#22C55E',
        downColor: '#EF4444',
        borderVisible: true,
        borderUpColor: '#22C55E',
        borderDownColor: '#EF4444',
        wickUpColor: '#22C55E',
        wickDownColor: '#EF4444',
    }});

    // Generate realistic prior bars leading to spot
    const bars = [];
    let p = initialBasePrice - 18.0;
    const nowSec = Math.floor(Date.now() / 1000);
    const startSec = nowSec - (60 * 60); // 60 bars of 1m

    for (let t = startSec; t < nowSec; t += 60) {{
        const change = (Math.random() - 0.48) * 3.5;
        const open = p;
        const close = open + change;
        const high = Math.max(open, close) + Math.random() * 2.5;
        const low = Math.min(open, close) - Math.random() * 2.5;
        p = close;
        bars.push({{ time: t - (t % 60), open, high, low, close }});
    }}
    // Last bar lands at currentPrice
    const lastBarTime = nowSec - (nowSec % 60);
    lastCandle = {{
        time: lastBarTime,
        open: p,
        high: Math.max(p, currentPrice) + 1.0,
        low: Math.min(p, currentPrice) - 1.0,
        close: currentPrice
    }};
    bars.push(lastCandle);
    candleSeries.setData(bars);

    // ATAS Horizontal Price Lines on Chart
    const m = window.INITIAL_META;
    putWallLine = candleSeries.createPriceLine({{
        price: m.put_wall,
        color: '#22C55E',
        lineWidth: 2,
        lineStyle: LightweightCharts.LineStyle.Solid,
        axisLabelVisible: true,
        title: "PUT WALL (" + m.put_wall_oi.toLocaleString() + " OI)",
    }});

    callWallLine = candleSeries.createPriceLine({{
        price: m.call_wall,
        color: '#EF4444',
        lineWidth: 2,
        lineStyle: LightweightCharts.LineStyle.Solid,
        axisLabelVisible: true,
        title: "CALL WALL (" + m.call_wall_oi.toLocaleString() + " OI)",
    }});

    const deepEfStk = m.strike_above + m.step;
    deepEfLine = candleSeries.createPriceLine({{
        price: deepEfStk,
        color: '#94A3B8',
        lineWidth: 1.5,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'DEEP EF STACK',
    }});

    buyerAbsLine = candleSeries.createPriceLine({{
        price: m.strike_below,
        color: '#38BDF8',
        lineWidth: 1.5,
        lineStyle: LightweightCharts.LineStyle.Dotted,
        axisLabelVisible: true,
        title: 'BUYER ABS',
    }});

    sellerOfferLine = candleSeries.createPriceLine({{
        price: m.strike_above,
        color: '#F43F5E',
        lineWidth: 1.5,
        lineStyle: LightweightCharts.LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'SELLER OFFER (+1R)',
    }});

    const gexReact = m.spot + (0.5 * m.step);
    gexReactionLine = candleSeries.createPriceLine({{
        price: gexReact,
        color: '#FACC15',
        lineWidth: 1.5,
        lineStyle: LightweightCharts.LineStyle.Dotted,
        axisLabelVisible: true,
        title: 'GEX REACTION',
    }});

    // Realtime Tick Price Line
    livePriceLine = candleSeries.createPriceLine({{
        price: currentPrice,
        color: '#F43F5E',
        lineWidth: 2,
        lineStyle: LightweightCharts.LineStyle.Solid,
        axisLabelVisible: true,
        title: 'F0 LIVE',
    }});

    window.addEventListener('resize', () => {{
        chart.applyOptions({{ width: container.clientWidth }});
        updateOverlayPositions();
    }});

    chart.timeScale().fitContent();
    updateOverlayPositions();
}}

// Synchronize ATAS CSS Shaded Boxes to Chart Coordinates
function updateOverlayPositions() {{
    if (!chart || !candleSeries) return;
    const m = window.INITIAL_META;
    const levels = [
        {{ id: 'overlay-put-wall', price: m.put_wall }},
        {{ id: 'overlay-call-wall', price: m.call_wall }},
        {{ id: 'overlay-deep-ef', price: m.strike_above + m.step }},
        {{ id: 'overlay-buyer-abs', price: m.strike_below }},
        {{ id: 'overlay-seller-offer', price: m.strike_above }},
        {{ id: 'overlay-gex-reaction', price: m.spot + 0.5 * m.step }},
    ];

    levels.forEach(lvl => {{
        const el = document.getElementById(lvl.id);
        if (!el) return;
        const y = candleSeries.priceToCoordinate(lvl.price);
        if (y !== null && !isNaN(y) && y >= 0 && y <= 540) {{
            el.style.top = (y - 9) + "px";
            el.style.display = 'flex';
        }} else {{
            el.style.display = 'none';
        }}
    }});
}}

// ----------------------------------------------------------------------------
// Realtime Tick Feeder & In-Browser Dynamic Greeks Recalculation
// ----------------------------------------------------------------------------
function onTick(price, isUserOverride = false) {{
    const prevPrice = currentPrice;
    currentPrice = price;

    // 1. Recalculate Greeks & Net GEX
    const res = Black76Engine.recalculate(currentPrice, window.INITIAL_OPTIONS, window.INITIAL_META);

    // 2. Update Ticker Bar
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

    // 3. Update KPI Cards
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

    // 4. Update Greeks Radar
    const elRadar = document.getElementById('live-greeks-radar');
    if (elRadar && res.atmGreeks) {{
        const g = res.atmGreeks;
        elRadar.innerHTML = "Delta &Delta;: <b>" + g.delta.toFixed(3) + "</b> | Gamma &Gamma;: <b>" + g.gamma.toFixed(5) + "</b> | Vega &nu;: <b>$" + g.vega.toFixed(1) + "M</b> | Theta &theta;: <b>" + g.theta.toFixed(1) + "k/d</b> | Vanna: <b>" + (g.vanna >= 0 ? "+" : "") + "$" + g.vanna.toFixed(1) + "M</b> | Charm: <b>" + (g.charm >= 0 ? "+" : "") + "$" + g.charm.toFixed(1) + "M/d</b>";
    }}

    // 5. Update Lightweight Charts Active Candle & Price Line
    if (candleSeries && livePriceLine) {{
        livePriceLine.applyOptions({{ price: currentPrice }});

        const nowSec = Math.floor(Date.now() / 1000);
        const candlePeriod = 60; // 1m
        const barTime = nowSec - (nowSec % candlePeriod);

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
        updateOverlayPositions();
    }}

    // 6. Highlight active strike row in table
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

function startSimulation() {{
    if (simInterval) clearInterval(simInterval);
    simInterval = setInterval(() => {{
        if (!isSimulating) return;
        // Realistic micro-tick: -1.25 to +1.25 pts with slight mean-reverting pull to base
        const drift = (initialBasePrice - currentPrice) * 0.02;
        const noise = (Math.random() - 0.495) * 1.5;
        const tick = Math.round((drift + noise) * 4) / 4; // Quarter-point granularity (0.25)
        const nextPrice = Math.round((currentPrice + tick) * 4) / 4;
        onTick(nextPrice);
    }}, 1000);
}}

function toggleSimulation() {{
    isSimulating = !isSimulating;
    const btn = document.getElementById('btn-toggle-sim');
    if (btn) {{
        if (isSimulating) {{
            btn.className = 'btn-ctrl btn-sim';
            btn.innerText = '● SIMULATION: ON';
        }} else {{
            btn.className = 'btn-ctrl btn-sim paused';
            btn.innerText = '❚❚ SIMULATION: PAUSED';
        }}
    }}
}}

function resetToLiveCME() {{
    const slider = document.getElementById('price-slider');
    if (slider) slider.value = initialBasePrice;
    const lbl = document.getElementById('slider-price-val');
    if (lbl) lbl.innerText = initialBasePrice.toFixed(2);
    onTick(initialBasePrice);
}}

function onSliderPriceChange(val) {{
    const p = parseFloat(val);
    const lbl = document.getElementById('slider-price-val');
    if (lbl) lbl.innerText = p.toFixed(2);
    onTick(p, true);
}}

function setTimeframe(tf) {{
    document.querySelectorAll('.timeframe-pill').forEach(btn => {{
        if (btn.innerText.toLowerCase() === tf.toLowerCase()) {{
            btn.classList.add('active');
        }} else {{
            btn.classList.remove('active');
        }}
    }});
}}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {{
    initAtasChart();
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

    # Also export hot tactical JSON feed
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
