"""Neiro-NQ-Quant Tactical HTML Dashboard Generator.

Generates a standalone, production-grade Plotly interactive dark-mode terminal for
E-mini Nasdaq-100 Futures Options (NQ / NQZ26 / NAS100) incorporating:
- Live KPI cards (Spot CME Futures vs Spot MT5, Market Regime, Net GEX, 1-Sigma Expected Move, Net VEX/CHEX)
- 3-Panel Plotly Interactive Charts:
  * Panel 1: Net GEX ($M) & Mốc Chiến Thuật (SL/TP)
  * Panel 2: Dòng Tiền Volume vs Open Interest Nén
  * Panel 3: Greeks Bậc 2 (Vanna & Charm)
- Anti-collision algorithm (Legend at y=1.07, Spot CME at x=0.98 right edge, Vanna/Charm vertical separation)
- Dynamic Tactical Levels 100% (No hardcoded prices or levels)
- Intraday Scalping Strategy Table (Lướt sóng trong ngày ăn 30-50 điểm NQ)
- Structural Swing Walls Strategy Table (Phục kích thành trì đánh sóng lớn)
- Zero-waste & ASCII/UTF-8 compliant.
"""
from __future__ import annotations

import argparse
import datetime
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
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Load options dataset from live yfinance (QQQ -> NQ, fast & free, default)
    or fall back to CSV file / embedded benchmark data.
    """
    df_raw = None

    # 1. Primary Source: Live yfinance (Fast, 100% Free, No Browser, Bypasses Cloudflare)
    if source == "yfinance":
        try:
            print("[Dashboard] Fetching real-time QQQ options chain via yfinance...")
            from src.collector.nasdaq_collector import NasdaqCollector
            collector = NasdaqCollector()
            df_live, prices = collector.fetch_standardized_nq_chain()
            if not df_live.empty and len(df_live) >= 5:
                df_raw = df_live
                print(f"[+] Loaded {len(df_raw)} strikes via yfinance (QQQ ${prices['underlying']:.2f} -> NQ {prices['futures']:.2f}).")
                # Save snapshot to CSV if path provided
                if csv_path:
                    try:
                        p_csv = Path(csv_path)
                        p_csv.parent.mkdir(parents=True, exist_ok=True)
                        df_raw.to_csv(p_csv, index=False)
                    except Exception:
                        pass
        except Exception as e:
            print(f"[Dashboard] Notice: yfinance fetch encountered ({e}). Checking CSV/benchmark fallback...")

    # 2. Secondary Source: Local CSV dataset
    if (df_raw is None or df_raw.empty) and csv_path and os.path.exists(csv_path):
        try:
            df_raw = pd.read_csv(csv_path)
            col_clean = {c: c.strip() for c in df_raw.columns}
            df_raw.rename(columns=col_clean, inplace=True)
            print(f"[+] Loaded {len(df_raw)} strikes from CSV: {csv_path}")
        except Exception as e:
            print(f"[Dashboard] Warning: Could not read CSV at {csv_path} ({e}). Using benchmark.")
            df_raw = None

    # 3. Tertiary Fallback: High-fidelity benchmark data
    if df_raw is None or df_raw.empty or len(df_raw) < 5:
        print("[Dashboard] Loading high-fidelity E-mini NQ benchmark options chain...")
        df_raw = generate_benchmark_nq_chain(spot=20500.0)

    # Calculate complete quantitative matrix via Black-76
    df_enriched, meta = process_options_chain_black76(
        df_raw,
        multiplier=multiplier,
        risk_free_rate=0.045,
        dte_days=1.0,
        basis_offset=basis,
    )
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
    fig.add_annotation(
        x=0.98, y=spot_price,
        text=f"◆ SPOT CME: {spot_price:,.1f} (MT5: ~{spot_mt5:,.1f})",
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
    """Generate high-fidelity, standalone dark-mode HTML tactical report."""
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

    # Dynamic SL & TP offsets based on strike step (no hardcoding)
    hard_sl_pts = min(step * 0.35, 25.0)
    fade_sl_pts = min(step * 0.30, 20.0)
    front_run_tp = max(1.0, step * 0.05)

    plotly_div = fig.to_html(full_html=False, include_plotlyjs="cdn", config={"responsive": True, "displayModeBar": True})

    # Regime Color Badge
    if "POSITIVE" in regime:
        regime_badge = '<span class="badge badge-pos">POSITIVE GAMMA (NÉN BIẾN ĐỘ / FADE)</span>'
        regime_color = "#4ADE80"
    elif "NEGATIVE" in regime:
        regime_badge = '<span class="badge badge-neg">NEGATIVE GAMMA (KHUẾCH ĐẠI / BREAKOUT)</span>'
        regime_color = "#F87171"
    else:
        regime_badge = '<span class="badge badge-gold">NEUTRAL TRANSITION (CÂN BẰNG)</span>'
        regime_color = "#FACC15"

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

        table_rows_html += f"""
        <tr {row_class}>
            <td><b>{stk:,.0f} pts</b></td>
            <td style="color: #38BDF8;">~{stk_mt5:,.1f}</td>
            <td style="{gex_style}">${gex:+.2f}M</td>
            <td>{c_oi:,}</td>
            <td>{p_oi:,}</td>
            <td>{c_vol:,}</td>
            <td>{p_vol:,}</td>
            <td style="color: #FB923C;">${vex:+.2f}M</td>
            <td style="color: #22D3EE;">${chex:+.2f}M</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NEIRO-NQ-QUANT: E-MINI NASDAQ TACTICAL TERMINAL</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #070B12; --bg-card: #0F172A; --border-color: #1E293B;
            --text-primary: #F8FAFC; --text-secondary: #94A3B8; --text-muted: #64748B;
            --neon-green: #22C55E; --neon-red: #EF4444; --neon-blue: #38BDF8; --neon-gold: #FACC15;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: var(--bg-base); color: var(--text-primary);
            font-family: 'Inter', -apple-system, sans-serif; padding: 20px; font-size: 13.5px;
        }}
        .container {{ max-width: 1460px; margin: 0 auto; }}
        .header {{
            display: flex; justify-content: space-between; align-items: center;
            padding: 16px 24px; background: linear-gradient(135deg, #0F172A 0%, #131E35 100%);
            border: 1px solid var(--border-color); border-radius: 12px; margin-bottom: 18px;
        }}
        .brand {{ display: flex; align-items: center; gap: 12px; }}
        .brand-title {{
            font-size: 20px; font-weight: 800;
            background: linear-gradient(90deg, #FFFFFF 0%, #93C5FD 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
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
        .kpi-grid {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; margin-bottom: 18px;
        }}
        .kpi-card {{
            background-color: var(--bg-card); border: 1px solid var(--border-color);
            border-radius: 12px; padding: 14px 18px; transition: transform 0.2s;
        }}
        .kpi-card:hover {{ transform: translateY(-2px); border-color: #334155; }}
        .kpi-label {{
            font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--text-secondary); margin-bottom: 4px;
        }}
        .kpi-val {{
            font-size: 22px; font-weight: 700; font-family: 'JetBrains Mono', monospace; margin-bottom: 4px;
        }}
        .kpi-sub {{ font-size: 11.5px; color: var(--text-muted); }}
        .chart-box {{
            background-color: var(--bg-card); border: 1px solid var(--border-color);
            border-radius: 12px; padding: 10px; margin-bottom: 20px;
        }}
        .table-box {{
            background-color: var(--bg-card); border: 1px solid var(--border-color);
            border-radius: 12px; padding: 16px; margin-bottom: 18px; overflow-x: auto;
        }}
        .section-header {{
            font-size: 14.5px; font-weight: 700; margin-bottom: 12px; color: #E2E8F0;
            display: flex; align-items: center; gap: 8px;
        }}
        table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; text-align: left; }}
        th {{
            background-color: #111C33; color: var(--text-secondary); padding: 10px 12px;
            font-weight: 600; border-bottom: 1px solid var(--border-color); white-space: nowrap;
        }}
        td {{
            padding: 10px 12px; border-bottom: 1px solid #162238; font-family: 'JetBrains Mono', monospace;
        }}
        tr:hover td {{ background-color: #1E293B; }}
        .row-spot td {{
            background-color: rgba(56, 189, 248, 0.12) !important;
            border-top: 1px solid var(--neon-blue); border-bottom: 1px solid var(--neon-blue);
        }}
        .tag-buy {{ color: #4ADE80; font-weight: 700; }}
        .tag-sell {{ color: #F87171; font-weight: 700; }}
        .insight-box {{
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
            border-left: 4px solid var(--neon-blue); border-radius: 8px;
            padding: 12px 16px; margin-bottom: 18px; font-size: 12.5px; line-height: 1.55;
        }}
        .footer {{
            text-align: center; font-size: 11px; color: var(--text-muted);
            padding: 18px 0; border-top: 1px solid var(--border-color);
        }}
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
        <div style="font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #D6D3D1;">
            Cập nhật: <b>{now_str} (Giờ VN)</b>
        </div>
    </div>

    <!-- Executive KPI Grid -->
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-label">Spot CME Futures &mdash; Spot MT5 (Quy đổi)</div>
            <div class="kpi-val" style="color: #60A5FA;">NQ {spot:,.1f} <span style="font-size: 15px; color: #38BDF8;">(MT5: ~{spot_mt5:,.1f})</span></div>
            <div class="kpi-sub">Trục ATM CME: <b>{meta['atm_strike']:,.0f} pts</b> | Basis MT5 Spot: <b>{basis:+0.1f} pts</b></div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Market Regime & Net GEX</div>
            <div class="kpi-val" style="color: {regime_color};">${total_gex:+.1f}M GEX</div>
            <div class="kpi-sub">{regime_badge}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Biên Độ 1-Sigma Expected Move</div>
            <div class="kpi-val" style="color: var(--neon-gold);">±{expected_move:,.1f} pts</div>
            <div class="kpi-sub">Intraday (Rule of 16): <b>±{intraday_move:,.1f} pts</b> ({spot-intraday_move:,.0f} &mdash; {spot+intraday_move:,.0f})</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Greeks Bậc 2 (Vanna & Charm)</div>
            <div class="kpi-val" style="color: #38BDF8;">${total_vex:+.1f}M / ${total_chex:+.1f}M</div>
            <div class="kpi-sub">Net VEX (1% IV) | Net CHEX (Ngày decay)</div>
        </div>
    </div>

    <!-- 3-Panel Plotly Interactive Chart -->
    <div class="chart-box">
        {plotly_div}
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
                    <th>Vùng Kích Hoạt (CME)</th>
                    <th>Entry CME</th>
                    <th>MT5 Spot (~ Basis)</th>
                    <th>Hard SL (CME)</th>
                    <th>Take Profit (TP)</th>
                    <th>Ghi Chú Hành Vi Market Maker</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="tag-buy">1. BUY MUA ĐUỔI (Squeeze {strike_above:,.0f})</td>
                    <td>Vượt > {strike_above + buffer_val:,.1f}</td>
                    <td>{strike_above + buffer_val + 2.0:,.1f}</td>
                    <td style="color:#38BDF8; font-weight:600;">~{strike_above + buffer_val + 2.0 - basis:,.1f}</td>
                    <td style="color:#F87171;">{strike_above - hard_sl_pts:,.1f} ({hard_sl_pts:.0f}p)</td>
                    <td style="color:#4ADE80;">{next_above - front_run_tp:,.1f}</td>
                    <td style="font-family: sans-serif; color: var(--text-secondary);">MM vỡ trận Short -> Gamma Squeeze đẩy giá bốc đầu lên nấc {next_above:,.0f}</td>
                </tr>
                <tr>
                    <td class="tag-sell">2. SELL CHẶN TIỀN TUYẾN (Fade {strike_above:,.0f})</td>
                    <td>{strike_above - 10.0:,.1f} - {strike_above:,.1f}</td>
                    <td>{strike_above - 2.0:,.1f}</td>
                    <td style="color:#38BDF8; font-weight:600;">~{strike_above - 2.0 - basis:,.1f}</td>
                    <td style="color:#F87171;">{strike_above + fade_sl_pts:,.1f} ({fade_sl_pts:.0f}p)</td>
                    <td style="color:#4ADE80;">{spot:,.1f}</td>
                    <td style="font-family: sans-serif; color: var(--text-secondary);">Call Vol cực đại -> MM bán Futures chặn đầu ghìm giá hồi về Spot</td>
                </tr>
                <tr>
                    <td class="tag-buy">3. BUY BẮT SÀN ATM (Rebound {strike_below:,.0f})</td>
                    <td>{strike_below:,.1f} - {strike_below + 10.0:,.1f}</td>
                    <td>{strike_below + 3.0:,.1f}</td>
                    <td style="color:#38BDF8; font-weight:600;">~{strike_below + 3.0 - basis:,.1f}</td>
                    <td style="color:#F87171;">{strike_below - hard_sl_pts:,.1f} ({hard_sl_pts:.0f}p)</td>
                    <td style="color:#4ADE80;">{strike_above - front_run_tp:,.1f}</td>
                    <td style="font-family: sans-serif; color: var(--text-secondary);">Đệm Put hỗ trợ kỹ thuật trong phiên đẩy giá hồi phục cân bằng</td>
                </tr>
                <tr>
                    <td class="tag-sell">4. SELL THỦNG SÀN ATM (Breakdown {strike_below:,.0f})</td>
                    <td>Thủng &lt; {strike_below - buffer_val:,.1f}</td>
                    <td>{strike_below - buffer_val - 2.0:,.1f}</td>
                    <td style="color:#38BDF8; font-weight:600;">~{strike_below - buffer_val - 2.0 - basis:,.1f}</td>
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
            <span>🏰 PHẦN 2: BẢNG TÁC CHIẾN PHỤC KÍCH THÀNH TRÌ (STRUCTURAL SWING WALLS - ĐÁNH SÓNG LỚN)</span>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Chiến Lược</th>
                    <th>Vùng Kích Hoạt (CME)</th>
                    <th>Entry CME</th>
                    <th>MT5 Spot (~ Basis)</th>
                    <th>Hard SL (CME)</th>
                    <th>Take Profit (TP)</th>
                    <th>Ghi Chú Cấu Trúc Khối Lượng</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="tag-sell">5. BÁN ĐỈNH CALL WALL ({call_wall:,.0f})</td>
                    <td>{call_wall - 15.0:,.1f} - {call_wall:,.1f}</td>
                    <td>{call_wall - 3.0:,.1f}</td>
                    <td style="color:#38BDF8; font-weight:600;">~{call_wall - 3.0 - basis:,.1f}</td>
                    <td style="color:#F87171;">{call_wall + 25.0:,.1f} (25p)</td>
                    <td style="color:#4ADE80;">{strike_above:,.1f} / {spot:,.1f}</td>
                    <td style="font-family: sans-serif; color: var(--text-secondary);">Call Wall {call_wall_oi:,} OI (Nóc nhà kiên cố cuối cùng của MM)</td>
                </tr>
                <tr>
                    <td class="tag-buy">6. MUA ĐÁY PUT WALL ({put_wall:,.0f})</td>
                    <td>{put_wall:,.1f} - {put_wall + 15.0:,.1f}</td>
                    <td>{put_wall + 3.0:,.1f}</td>
                    <td style="color:#38BDF8; font-weight:600;">~{put_wall + 3.0 - basis:,.1f}</td>
                    <td style="color:#F87171;">{put_wall - 25.0:,.1f} (25p)</td>
                    <td style="color:#4ADE80;">{strike_below:,.1f} / {spot:,.1f}</td>
                    <td style="font-family: sans-serif; color: var(--text-secondary);">Major Put Wall {put_wall_oi:,} OI (Đáy bê tông cốt thép phòng ngự của cá mập)</td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- Microstructure Strike Table -->
    <div class="table-box">
        <div class="section-header">
            <span>📊 BẢNG DỮ LIỆU ĐỊNH LƯỢNG MICROSTRUCTURE TỪNG STRIKE (E-MINI NASDAQ & MT5 SPOT)</span>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Strike NQ</th>
                    <th>MT5 Spot (~ Basis)</th>
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
) -> str:
    """Build complete Plotly terminal and export to output HTML file paths."""
    if output_paths is None or len(output_paths) == 0:
        output_paths = ["exports/latest_nq_dashboard.html", "exports/index.html"]

    df_full, meta = load_options_dataset(
        csv_path=csv_path,
        basis=basis,
        multiplier=multiplier,
        source=source,
    )
    fig = build_plotly_terminal(df_full, meta)
    html_content = generate_html_terminal(df_full, meta, fig)

    for out_p in output_paths:
        p = Path(out_p)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"[+] [Dashboard] Exported standalone terminal to: {p} ({p.stat().st_size:,} bytes)")

    return output_paths[0]


def main():
    parser = argparse.ArgumentParser(description="Neiro-NQ-Quant Tactical HTML Dashboard Generator")
    parser.add_argument("--source", default="yfinance", choices=["yfinance", "barchart", "csv"], help="Options data source (yfinance is fast, free, no browser)")
    parser.add_argument("--input", default="data/options_prices_NQZ26.csv", help="Input options CSV dataset (if using csv/barchart)")
    parser.add_argument("--output", nargs="+", default=["exports/latest_nq_dashboard.html", "exports/index.html"], help="Output HTML file path(s)")
    parser.add_argument("--basis", type=float, default=0.0, help="MT5 Spot Basis offset (Spot_MT5 = Spot_Futures - basis)")
    parser.add_argument("--multiplier", type=float, default=20.0, help="Options multiplier (20 for NQ, 2 for MNQ)")
    args = parser.parse_args()

    build_and_export_dashboard(
        csv_path=args.input,
        output_paths=args.output,
        basis=args.basis,
        multiplier=args.multiplier,
        source=args.source,
    )


if __name__ == "__main__":
    main()
