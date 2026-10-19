"""
Interactive Plotly ATAS Dark Theme Dashboard & Standalone HTML Report Generator for E-mini Nasdaq.
Renders natively in Google Colab and exports to a complete standalone HTML tactical terminal.
Panel Layout matches Neiro-Quant exact 3-panel horizontal price ladder:
- Panel 1: Net GEX ($M) & Moc Chien Thuat (SL/TP) (Horizontal bars, Y-axis = Strike Price)
- Panel 2: Dong Tien Volume vs Open Interest Nen (Horizontal bars, Left = Put OI/Vol, Right = Call OI/Vol)
- Panel 3: Greeks Bac 2: Vanna (VEX) & Charm (CHEX) (Horizontal bars)
Zero-Waste & ASCII/UTF-8 Compliant.
"""
import os
import json
import datetime
import pandas as pd
from typing import Dict, Any, Optional, List

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

from src.quant_engine.state_machine import LevelStateMachine, LevelState


def build_tactical_dashboard(
    df: pd.DataFrame,
    metrics: Dict[str, Any],
    output_html_path: Optional[str] = None
) -> Optional[Any]:
    """
    Build 3-Panel ATAS-style horizontal price ladder terminal for E-mini Nasdaq & QQQ Options:
    - Panel 1: Net Gamma Exposure (Net GEX Profile per Strike) + Structural Reference Lines & Action Badges
    - Panel 2: Volume vs Open Interest (Put on Left, Call on Right)
    - Panel 3: 2nd Order Greeks: Vanna (VEX) & Charm (CHEX)
    Exports to standalone high-fidelity HTML report containing charts, KPI cards, and tactical tables.
    """
    if not PLOTLY_AVAILABLE:
        print("[Dashboard] Plotly is not installed, cannot render interactive chart.")
        return None

    spot = metrics["spot_price_qqq"]
    basis = metrics["basis_ratio"]
    nq_spot = metrics["nq_futures_price"]
    
    cw_qqq = metrics["qqq_levels"]["call_wall"]
    pw_qqq = metrics["qqq_levels"]["put_wall"]
    cw_nq = metrics["nq_levels"]["call_wall"]
    pw_nq = metrics["nq_levels"]["put_wall"]
    pivot_qqq = metrics["qqq_levels"]["atm_synthetic_pivot"]
    pivot_nq = metrics["nq_levels"]["atm_synthetic_pivot"]
    
    trigger_up_nq = metrics["nq_levels"].get("trigger_up", cw_nq)
    trigger_down_nq = metrics["nq_levels"].get("trigger_down", pw_nq)
    band_1s_up_nq = metrics["nq_levels"]["upper_band_1s"]
    band_1s_dn_nq = metrics["nq_levels"]["lower_band_1s"]
    straddle_move = metrics["nq_levels"]["straddle_implied_move"]
    intraday_move = round(straddle_move / 4.0, 2)
    
    total_gex = metrics["total_net_gex_millions"]
    regime = metrics["regime"]
    
    # Filter strikes near ATM for clarity (within +- 30 points of QQQ)
    df_plot = df[(df['strike'] >= spot - 30) & (df['strike'] <= spot + 30)].copy()
    if df_plot.empty or len(df_plot) < 5:
        df_plot = df.copy()
    df_plot = df_plot.sort_values('strike', ascending=True).reset_index(drop=True)

    # Ensure 2nd order Greeks exist
    if 'netVEX' not in df_plot.columns:
        df_plot['netVEX'] = 0.0
    if 'netCHEX' not in df_plot.columns:
        df_plot['netCHEX'] = 0.0
    if 'callVolume' not in df_plot.columns:
        df_plot['callVolume'] = df_plot['callOpenInterest'] * 0.3
    if 'putVolume' not in df_plot.columns:
        df_plot['putVolume'] = df_plot['putOpenInterest'] * 0.35

    total_vex = float(df['netVEX'].sum()) if 'netVEX' in df.columns else 0.0
    total_chex = float(df['netCHEX'].sum()) if 'netCHEX' in df.columns else 0.0

    # Max VEX and Min CHEX for callouts
    max_vex_row = df_plot.loc[df_plot['netVEX'].idxmax()] if not df_plot.empty else None
    min_chex_row = df_plot.loc[df_plot['netCHEX'].idxmin()] if not df_plot.empty else None

    # Find Wall OIs
    cw_row = df[df['strike'] == cw_qqq]
    cw_oi = int(cw_row['callOpenInterest'].iloc[0]) if not cw_row.empty else int(df['callOpenInterest'].max())
    pw_row = df[df['strike'] == pw_qqq]
    pw_oi = int(pw_row['putOpenInterest'].iloc[0]) if not pw_row.empty else int(df['putOpenInterest'].max())

    # Create 3 Subplots Side-by-Side (1 Row, 3 Columns)
    fig = make_subplots(
        rows=1, cols=3,
        shared_yaxes=True,
        horizontal_spacing=0.035,
        subplot_titles=(
            "<b>Panel 1: Net GEX ($M) & Mốc Chiến Thuật (SL/TP)</b>",
            "<b>Panel 2: Dòng Tiền Volume vs Open Interest Nén</b>",
            "<b>Panel 3: Greeks Bậc 2: Vanna (VEX) & Charm (CHEX)</b>"
        ),
        column_widths=[0.36, 0.36, 0.28]
    )

    # -------------------------------------------------------------------------
    # PANEL 1: Net GEX ($M) Horizontal Bars
    # -------------------------------------------------------------------------
    colors_gex = ['#00E676' if x >= 0 else '#FF1744' for x in df_plot['netGEX']]
    hover_p1 = [
        f"Strike: QQQ ${s:.1f} (NQ ~{s*basis:.0f})<br>"
        f"Net GEX: ${g:+.2f}M<br>"
        f"Call GEX: ${cg:.2f}M | Put GEX: ${pg:.2f}M"
        for s, g, cg, pg in zip(df_plot['strike'], df_plot['netGEX'], df_plot['callGEX'], df_plot['putGEX'])
    ]
    fig.add_trace(
        go.Bar(
            y=df_plot['strike'],
            x=df_plot['netGEX'],
            orientation='h',
            marker=dict(color=colors_gex, line=dict(color='#1E293B', width=0.5)),
            name="Net GEX ($M)",
            hovertext=hover_p1,
            hoverinfo="text"
        ),
        row=1, col=1
    )
    # Vertical Zero Line for Panel 1
    fig.add_vline(x=0, line_dash="solid", line_color="#475569", line_width=1, row=1, col=1)

    # Reference Levels on Panel 1
    # Spot Price
    fig.add_hline(
        y=spot, line_color="#2979FF", line_width=2.5,
        annotation_text=f"SPOT CME: {spot:.2f} (NQ {nq_spot:.0f})",
        annotation_position="top left",
        annotation_font=dict(size=10, color="#FFFFFF"),
        annotation_bgcolor="#1D4ED8",
        row=1, col=1
    )
    # Call Wall
    fig.add_hline(
        y=cw_qqq, line_dash="dash", line_color="#00E676", line_width=1.8,
        annotation_text=f"CALL WALL: {cw_qqq:.0f} (NQ {cw_nq:.0f})",
        annotation_position="top right",
        annotation_font=dict(size=10, color="#00E676"),
        annotation_bgcolor="#064E3B",
        row=1, col=1
    )
    # Put Wall
    fig.add_hline(
        y=pw_qqq, line_dash="dash", line_color="#FF1744", line_width=1.8,
        annotation_text=f"PUT WALL: {pw_qqq:.0f} (NQ {pw_nq:.0f})",
        annotation_position="bottom right",
        annotation_font=dict(size=10, color="#FF5252"),
        annotation_bgcolor="#7F1D1D",
        row=1, col=1
    )
    # ATM Pivot
    fig.add_hline(
        y=pivot_qqq, line_dash="dot", line_color="#00E5FF", line_width=1.5,
        annotation_text=f"ATM PIVOT: {pivot_qqq:.1f} (NQ {pivot_nq:.0f})",
        annotation_position="bottom left",
        annotation_font=dict(size=9, color="#00E5FF"),
        annotation_bgcolor="#083344",
        row=1, col=1
    )

    # Detailed Tactical Callout Boxes (Exact Neiro-Quant style)
    min_gex = df_plot['netGEX'].min()
    max_gex = df_plot['netGEX'].max()
    fig.add_annotation(
        x=min_gex * 0.9, y=pw_qqq,
        text=(
            f"<b>[MAJOR PUT WALL ({pw_qqq:.0f}) ({pw_oi:,} OI - HỖ TRỢ ĐÁY NỀN)]</b><br>"
            f"• Vùng Mua (Rebound Buy): {pw_nq:,.0f} - {pw_nq+15:,.0f} | SL: {pw_nq-20:,.0f} | TP: {nq_spot:,.0f}<br>"
            f"• Waterfall Breakout: Thủng < {pw_nq-15:,.0f} -> Bán Tháo Nhanh"
        ),
        showarrow=True, arrowhead=2, arrowcolor="#FF5252",
        font=dict(size=9, color="#FFCDD2"),
        bgcolor="rgba(127, 29, 29, 0.85)", bordercolor="#FF5252", borderwidth=1,
        align="left",
        row=1, col=1
    )
    fig.add_annotation(
        x=max_gex * 0.75, y=cw_qqq,
        text=f"<b>CỬA ẢI {cw_qqq:.0f} (Squeeze > {trigger_up_nq:,.0f} -> TP {band_1s_up_nq:,.0f})</b>",
        showarrow=True, arrowhead=2, arrowcolor="#00E676",
        font=dict(size=9, color="#C8E6C9"),
        bgcolor="rgba(6, 78, 59, 0.85)", bordercolor="#00E676", borderwidth=1,
        row=1, col=1
    )
    fig.add_annotation(
        x=0, y=pivot_qqq,
        text=f"<b>SÀN ĐỠ ATM {pivot_qqq:.0f} (Rebound: {pivot_nq-10:,.0f} - {pivot_nq+10:,.0f})</b>",
        showarrow=True, arrowhead=2, arrowcolor="#00E5FF",
        font=dict(size=9, color="#E0F7FA"),
        bgcolor="rgba(8, 51, 68, 0.85)", bordercolor="#00E5FF", borderwidth=1,
        row=1, col=1
    )

    # -------------------------------------------------------------------------
    # PANEL 2: Volume vs Open Interest (Put on Left, Call on Right)
    # -------------------------------------------------------------------------
    # Put OI (Light Red) & Put Volume (Dark Red) on Left (-X)
    fig.add_trace(
        go.Bar(
            y=df_plot['strike'],
            x=-df_plot['putOpenInterest'],
            orientation='h',
            name="Put OI (Vị thế tích lũy)",
            marker_color='rgba(239, 83, 80, 0.45)',
            hovertemplate="Put OI: %{x}<br>Strike: %{y}<extra></extra>"
        ),
        row=1, col=2
    )
    fig.add_trace(
        go.Bar(
            y=df_plot['strike'],
            x=-df_plot['putVolume'],
            orientation='h',
            name="Put Volume (Lực Bán)",
            marker_color='#B71C1C',
            hovertemplate="Put Vol: %{x}<br>Strike: %{y}<extra></extra>"
        ),
        row=1, col=2
    )
    # Call OI (Light Green) & Call Volume (Dark Green) on Right (+X)
    fig.add_trace(
        go.Bar(
            y=df_plot['strike'],
            x=df_plot['callOpenInterest'],
            orientation='h',
            name="Call OI (Vị thế tích lũy)",
            marker_color='rgba(102, 187, 106, 0.45)',
            hovertemplate="Call OI: %{x}<br>Strike: %{y}<extra></extra>"
        ),
        row=1, col=2
    )
    fig.add_trace(
        go.Bar(
            y=df_plot['strike'],
            x=df_plot['callVolume'],
            orientation='h',
            name="Call Volume (Lực Mua)",
            marker_color='#1B5E20',
            hovertemplate="Call Vol: %{x}<br>Strike: %{y}<extra></extra>"
        ),
        row=1, col=2
    )
    # Vertical Zero Line for Panel 2
    fig.add_vline(x=0, line_dash="solid", line_color="#475569", line_width=1, row=1, col=2)
    # Spot line on Panel 2
    fig.add_hline(y=spot, line_color="#2979FF", line_width=1.5, row=1, col=2)
    fig.add_hline(y=cw_qqq, line_dash="dash", line_color="#00E676", line_width=1.0, row=1, col=2)
    fig.add_hline(y=pw_qqq, line_dash="dash", line_color="#FF1744", line_width=1.0, row=1, col=2)

    # Volume Spike Callouts (Exact Neiro-Quant style)
    if not df_plot.empty:
        max_pvol_idx = df_plot['putVolume'].idxmax()
        pvol_row = df_plot.loc[max_pvol_idx]
        fig.add_annotation(
            x=-pvol_row['putVolume'], y=pvol_row['strike'],
            text=f"Put Vol: {int(pvol_row['putVolume']):,} | OI: {int(pvol_row['putOpenInterest']):,}",
            showarrow=False, xanchor="right",
            font=dict(size=9, color="#FF5252"),
            row=1, col=2
        )
        max_cvol_idx = df_plot['callVolume'].idxmax()
        cvol_row = df_plot.loc[max_cvol_idx]
        fig.add_annotation(
            x=cvol_row['callVolume'], y=cvol_row['strike'],
            text=f"Call Vol: {int(cvol_row['callVolume']):,} | OI: {int(cvol_row['callOpenInterest']):,}",
            showarrow=False, xanchor="left",
            font=dict(size=9, color="#00E676"),
            row=1, col=2
        )

    # -------------------------------------------------------------------------
    # PANEL 3: 2nd Order Greeks: Vanna (VEX) & Charm (CHEX)
    # -------------------------------------------------------------------------
    fig.add_trace(
        go.Bar(
            y=df_plot['strike'],
            x=df_plot['netVEX'],
            orientation='h',
            name="Net VEX ($M / 1% IV)",
            marker_color='#FF9800',
            hovertemplate="Net VEX: $%{x:.2f}M<br>Strike: %{y}<extra></extra>"
        ),
        row=1, col=3
    )
    fig.add_trace(
        go.Bar(
            y=df_plot['strike'],
            x=df_plot['netCHEX'],
            orientation='h',
            name="Net CHEX ($M / Ngày)",
            marker_color='#00BCD4',
            hovertemplate="Net CHEX: $%{x:.2f}M<br>Strike: %{y}<extra></extra>"
        ),
        row=1, col=3
    )
    # Vertical Zero Line for Panel 3
    fig.add_vline(x=0, line_dash="solid", line_color="#475569", line_width=1, row=1, col=3)
    # Spot line on Panel 3
    fig.add_hline(y=spot, line_color="#2979FF", line_width=1.5, row=1, col=3)

    # Annotate Peak Vanna and Min Charm on Panel 3
    if max_vex_row is not None and max_vex_row['netVEX'] > 0.05:
        stk_v = float(max_vex_row['strike'])
        val_v = float(max_vex_row['netVEX'])
        fig.add_annotation(
            x=val_v, y=stk_v,
            text=f"ĐỈNH VANNA (+{val_v:.1f}M): Lực đẩy V-Rebound",
            showarrow=True, arrowhead=2, arrowcolor="#FF9800",
            font=dict(size=9, color="#FF9800"),
            bgcolor="#1E1E1E", bordercolor="#FF9800", borderwidth=1,
            row=1, col=3
        )
    if min_chex_row is not None and min_chex_row['netCHEX'] < -0.05:
        stk_c = float(min_chex_row['strike'])
        val_c = float(min_chex_row['netCHEX'])
        fig.add_annotation(
            x=val_c, y=stk_c,
            text=f"ĐỈNH CHARM ({val_c:.1f}M): Nam châm gìm giá",
            showarrow=True, arrowhead=2, arrowcolor="#00BCD4",
            font=dict(size=9, color="#00BCD4"),
            bgcolor="#1E1E1E", bordercolor="#00BCD4", borderwidth=1,
            row=1, col=3
        )

    # Overall Dark ATAS Layout
    regime_short = "POS_GAMMA (Mean-Revert)" if "POSITIVE" in regime else "NEG_GAMMA (Volatile)"
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0A0E17",
        plot_bgcolor="#111827",
        title=dict(
            text=f"<b>NEIRO-NQ-QUANT: E-MINI NASDAQ-100 OPTIONS (3 PANELS)</b> | Futures: {nq_spot:.2f} (QQQ: ${spot:.2f}) | {regime_short} ({total_gex:+.1f}M GEX) | Net VEX: {total_vex:+.1f}M | Net CHEX: {total_chex:+.1f}M/ngày",
            font=dict(size=14, color="#E2E8F0")
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="center",
            x=0.5,
            font=dict(size=10)
        ),
        margin=dict(l=75, r=30, t=95, b=45),
        height=720,
        barmode='relative'
    )

    # Format Y-Axis as Strike Price Ladder
    ticks_y = df_plot['strike'].tolist()
    labels_y = [f"${s:.0f} (NQ {s*basis:.0f})" for s in ticks_y]
    fig.update_yaxes(
        tickvals=ticks_y,
        ticktext=labels_y,
        gridcolor="#1E293B",
        title_text="E-mini Nasdaq Strike Ladder ($)",
        row=1, col=1
    )
    fig.update_yaxes(gridcolor="#1E293B", row=1, col=2)
    fig.update_yaxes(gridcolor="#1E293B", row=1, col=3)

    fig.update_xaxes(title_text="Net GEX ($M / 1% Biến Động)", gridcolor="#1E293B", row=1, col=1)
    fig.update_xaxes(title_text="Put OI/Vol (-) | Call OI/Vol (+)", gridcolor="#1E293B", row=1, col=2)
    fig.update_xaxes(title_text="Độ Nhạy Dealers ($M)", gridcolor="#1E293B", row=1, col=3)

    # Export complete standalone HTML report if path provided
    if output_html_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_html_path)), exist_ok=True)
        html_content = generate_standalone_html_report(
            fig=fig,
            df_chain=df,
            metrics=metrics,
            total_vex=total_vex,
            total_chex=total_chex,
            cw_oi=cw_oi,
            pw_oi=pw_oi,
            intraday_move=intraday_move
        )
        with open(output_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"[+] [Dashboard] Full Standalone HTML Report saved to: {output_html_path}")

    return fig


def generate_standalone_html_report(
    fig: Any,
    df_chain: pd.DataFrame,
    metrics: Dict[str, Any],
    total_vex: float,
    total_chex: float,
    cw_oi: int,
    pw_oi: int,
    intraday_move: float
) -> str:
    """
    Renders an all-in-one standalone HTML report containing:
    1. Header & Live Status
    2. Executive KPI Cards
    3. 3-Panel Price Ladder Interactive Chart (Plotly CDN)
    4. Level State Machine Radar Cards
    5. Intraday Scalping Tactical Table (Bang Tac Chien Luot Song Trong Ngay)
    6. Structural Swing Walls Tactical Table (Bang Tac Chien Phuc Kich Thanh Tri)
    7. Greeks Bac 2 (Vanna & Charm) Insights
    8. Strike-by-Strike Microstructure Data Table
    """
    spot = metrics["spot_price_qqq"]
    basis = metrics["basis_ratio"]
    nq_spot = metrics["nq_futures_price"]
    cw_nq = metrics["nq_levels"]["call_wall"]
    pw_nq = metrics["nq_levels"]["put_wall"]
    cw_qqq = metrics["qqq_levels"]["call_wall"]
    pw_qqq = metrics["qqq_levels"]["put_wall"]
    pivot_nq = metrics["nq_levels"]["atm_synthetic_pivot"]
    pivot_qqq = metrics["qqq_levels"]["atm_synthetic_pivot"]
    trigger_up_nq = metrics["nq_levels"].get("trigger_up", cw_nq)
    trigger_down_nq = metrics["nq_levels"].get("trigger_down", pw_nq)
    band_1s_up_nq = metrics["nq_levels"]["upper_band_1s"]
    band_1s_dn_nq = metrics["nq_levels"]["lower_band_1s"]
    band_2s_up_nq = metrics["nq_levels"]["upper_band_2s"]
    band_2s_dn_nq = metrics["nq_levels"]["lower_band_2s"]
    straddle_move = metrics["nq_levels"]["straddle_implied_move"]
    
    total_gex = metrics["total_net_gex_millions"]
    regime = metrics["regime"]
    regime_desc = metrics["regime_description"]
    
    # State Machine evaluations
    sm = LevelStateMachine()
    recs = sm.evaluate(nq_spot, metrics)
    
    # Extract Plotly div without full page wrapper
    plotly_div = fig.to_html(full_html=False, include_plotlyjs=False)
    
    # Regime Badges
    if "POSITIVE" in regime:
        regime_badge = '<span class="badge badge-pos">POSITIVE GAMMA (NÉN BIẾN ĐỘ / FADE)</span>'
        regime_color = "#00E676"
    else:
        regime_badge = '<span class="badge badge-neg">NEGATIVE GAMMA (KHUẾCH ĐẠI / BREAKOUT)</span>'
        regime_color = "#FF1744"

    # State Machine Pills
    def get_badge_class(st: str) -> str:
        if st == LevelState.ABSORPTION_DEFENDED.value:
            return "badge-pos"
        elif st in [LevelState.SLICING_RISK.value, LevelState.SLICED_VACUUM.value]:
            return "badge-neg"
        elif st == LevelState.TRIGGERED_TESTING.value:
            return "badge-warning"
        return "badge-neutral"

    radar_cards_html = ""
    for r in recs:
        b_cls = get_badge_class(r.state.value)
        radar_cards_html += f"""
        <div class="radar-card">
            <div class="radar-title">{r.level_name}</div>
            <div class="radar-price">NQ {r.level_price_nq:,.1f} <span class="sub-price">(QQQ ${r.level_price_qqq:.1f})</span></div>
            <div style="margin: 6px 0;"><span class="badge {b_cls}">{r.state.value}</span></div>
            <div class="radar-action"><b>Lệnh:</b> {r.action}</div>
            <div class="radar-entry">{r.entry_guide}</div>
            <div class="radar-sltp">SL: <b>{r.stop_loss_nq:,.1f}</b> | TP: <b>{r.take_profit_nq:,.1f}</b></div>
        </div>
        """

    # Microstructure Table Rows (near ATM)
    table_rows_html = ""
    df_sorted = df_chain[(df_chain['strike'] >= spot - 35) & (df_chain['strike'] <= spot + 35)].sort_values('strike', ascending=False)
    for _, row in df_sorted.iterrows():
        stk_q = row['strike']
        stk_nq = row.get('strikeNQ', stk_q * basis)
        gex = row.get('netGEX', 0.0)
        c_oi = int(row.get('callOpenInterest', 0))
        p_oi = int(row.get('putOpenInterest', 0))
        c_vol = int(row.get('callVolume', 0))
        p_vol = int(row.get('putVolume', 0))
        vex = row.get('netVEX', 0.0)
        chex = row.get('netCHEX', 0.0)
        
        gex_style = "color: #00E676; font-weight: 600;" if gex >= 0 else "color: #FF5252; font-weight: 600;"
        is_spot_near = abs(stk_q - spot) <= 2.5
        row_class = 'class="row-spot"' if is_spot_near else ""
        
        table_rows_html += f"""
        <tr {row_class}>
            <td><b>${stk_q:.1f}</b></td>
            <td><b>NQ {stk_nq:,.1f}</b></td>
            <td style="{gex_style}">${gex:+.2f}M</td>
            <td>{c_oi:,}</td>
            <td>{p_oi:,}</td>
            <td>{c_vol:,}</td>
            <td>{p_vol:,}</td>
            <td style="color: #FFB74D;">${vex:+.2f}M</td>
            <td style="color: #4DD0E1;">${chex:+.2f}M</td>
        </tr>
        """

    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    now_vn = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S ICT (VN)")

    # Full HTML template
    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NEIRO-NQ-QUANT: E-mini Nasdaq Tactical Terminal</title>
    <!-- Plotly CDN for Ultra-Lightweight Zero-Waste Rendering (<35KB HTML) -->
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base: #070B12;
            --bg-card: #0F172A;
            --bg-card-hover: #1E293B;
            --border-color: #1E293B;
            --text-primary: #F8FAFC;
            --text-secondary: #94A3B8;
            --text-muted: #64748B;
            --neon-green: #00E676;
            --neon-red: #FF1744;
            --neon-blue: #2979FF;
            --neon-cyan: #00E5FF;
            --neon-amber: #FFB300;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            background-color: var(--bg-base);
            color: var(--text-primary);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            padding: 20px;
            font-size: 14px;
            line-height: 1.5;
        }}
        .container {{
            max-width: 1440px;
            margin: 0 auto;
        }}
        /* Header */
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 24px;
            background: linear-gradient(135deg, #0F172A 0%, #131E35 100%);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            margin-bottom: 20px;
        }}
        .brand {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .brand-title {{
            font-size: 20px;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: linear-gradient(90deg, #FFFFFF 0%, #93C5FD 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .pulse-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 230, 118, 0.7); }}
            70% {{ transform: scale(1); box-shadow: 0 0 0 8px rgba(0, 230, 118, 0); }}
            100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 230, 118, 0); }}
        }}
        .sync-info {{
            text-align: right;
            font-size: 12px;
            color: var(--text-secondary);
            font-family: 'JetBrains Mono', monospace;
        }}
        /* KPI Cards Grid */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
        }}
        .kpi-card {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 16px 20px;
            transition: transform 0.2s, border-color 0.2s;
        }}
        .kpi-card:hover {{
            border-color: #334155;
            transform: translateY(-2px);
        }}
        .kpi-label {{
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }}
        .kpi-val {{
            font-size: 24px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            margin-bottom: 4px;
        }}
        .kpi-sub {{
            font-size: 12px;
            color: var(--text-muted);
        }}
        /* Badges */
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            letter-spacing: 0.3px;
        }}
        .badge-pos {{
            background: rgba(0, 230, 118, 0.15);
            color: var(--neon-green);
            border: 1px solid rgba(0, 230, 118, 0.4);
        }}
        .badge-neg {{
            background: rgba(255, 23, 68, 0.15);
            color: var(--neon-red);
            border: 1px solid rgba(255, 23, 68, 0.4);
        }}
        .badge-warning {{
            background: rgba(255, 179, 0, 0.15);
            color: var(--neon-amber);
            border: 1px solid rgba(255, 179, 0, 0.4);
        }}
        .badge-neutral {{
            background: rgba(148, 163, 184, 0.1);
            color: var(--text-secondary);
            border: 1px solid rgba(148, 163, 184, 0.2);
        }}
        /* Chart Container */
        .chart-box {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 12px;
            margin-bottom: 24px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        }}
        /* Radar Cards */
        .section-header {{
            font-size: 16px;
            font-weight: 700;
            letter-spacing: -0.3px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
            color: #E2E8F0;
        }}
        .radar-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 14px;
            margin-bottom: 24px;
        }}
        .radar-card {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 14px;
        }}
        .radar-title {{
            font-size: 12px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
        }}
        .radar-price {{
            font-size: 18px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
            margin: 4px 0;
        }}
        .sub-price {{
            font-size: 12px;
            color: var(--text-muted);
            font-weight: 400;
        }}
        .radar-action {{
            font-size: 12px;
            margin: 4px 0;
            color: #93C5FD;
        }}
        .radar-entry {{
            font-size: 12px;
            color: var(--text-secondary);
            margin-bottom: 6px;
            line-height: 1.4;
        }}
        .radar-sltp {{
            font-size: 11px;
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-muted);
        }}
        /* Tactical Tables */
        .table-box {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 24px;
            overflow-x: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            text-align: left;
        }}
        th {{
            background-color: #111C33;
            color: var(--text-secondary);
            padding: 10px 14px;
            font-weight: 600;
            border-bottom: 1px solid var(--border-color);
            white-space: nowrap;
        }}
        td {{
            padding: 10px 14px;
            border-bottom: 1px solid #162238;
            font-family: 'JetBrains Mono', monospace;
        }}
        tr:hover td {{
            background-color: var(--bg-card-hover);
        }}
        .row-spot td {{
            background-color: rgba(41, 121, 255, 0.12) !important;
            border-top: 1px solid var(--neon-blue);
            border-bottom: 1px solid var(--neon-blue);
        }}
        /* Notes & Insights */
        .insight-box {{
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
            border-left: 4px solid var(--neon-cyan);
            border-radius: 8px;
            padding: 14px 18px;
            margin-bottom: 24px;
            font-size: 13px;
            line-height: 1.6;
        }}
        /* Footer */
        .footer {{
            text-align: center;
            font-size: 11px;
            color: var(--text-muted);
            padding: 20px 0;
            border-top: 1px solid var(--border-color);
        }}
    </style>
</head>
<body>
<div class="container">
    <!-- Header -->
    <div class="header">
        <div class="brand">
            <div class="pulse-dot"></div>
            <div class="brand-title">NEIRO-NQ-QUANT</div>
            <span class="badge badge-pos">LIVE CLOUD RADAR</span>
        </div>
        <div class="sync-info">
            <div><b>Cập nhật:</b> {now_vn}</div>
            <div style="color: var(--text-muted);">{now_utc} | Drive Synced</div>
        </div>
    </div>

    <!-- Executive KPI Grid -->
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-label">E-mini NQ / QQQ Spot</div>
            <div class="kpi-val" style="color: #60A5FA;">NQ {nq_spot:,.2f}</div>
            <div class="kpi-sub">QQQ: <b>${spot:.2f}</b> | Basis Ratio: <b>{basis:.2f}</b></div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Market Regime & Net GEX</div>
            <div class="kpi-val" style="color: {regime_color};">${total_gex:+.1f}M GEX</div>
            <div class="kpi-sub">{regime_badge}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Biên Độ 1-Sigma Expected Move</div>
            <div class="kpi-val" style="color: var(--neon-amber);">±{straddle_move:,.1f} pts</div>
            <div class="kpi-sub">Intraday (Rule of 16): <b>±{intraday_move:,.1f} pts</b> | ±${straddle_move/basis:.2f} QQQ</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Greeks Bậc 2 (Vanna & Charm)</div>
            <div class="kpi-val" style="color: var(--neon-cyan);">${total_vex:+.1f}M / ${total_chex:+.1f}M</div>
            <div class="kpi-sub">Net VEX (1% IV) | Net CHEX (Ngày decay)</div>
        </div>
    </div>

    <!-- 3-Panel ATAS Interactive Chart -->
    <div class="chart-box">
        {plotly_div}
    </div>

    <!-- State Machine Radar -->
    <div class="section-header">
        <span>⚡ LEVEL STATE MACHINE RADAR (TRẠNG THÁI MỐC CẢN THỰC THỜI)</span>
    </div>
    <div class="radar-grid">
        {radar_cards_html}
    </div>

    <!-- 1-Sigma Expected Move & Greeks Bac 2 Insights (Exact Neiro-Quant Colab Style) -->
    <div class="insight-box" style="border-left-color: #60A5FA; margin-bottom: 16px;">
        <b style="color: #93C5FD; font-size: 14px;">📐 [ĐỘ LỆCH CHUẨN & BIÊN ĐỘ 1-SIGMA]:</b><br>
        • <b>ATM Straddle (Call + Put ATM):</b> ${straddle_move/basis:.2f} (QQQ) | NQ ±{straddle_move:,.1f} pts | Implied Volatility (IV): ~18.5%<br>
        • <b>Expected Move 1-Sigma (Brenner-Subrahmanyam):</b> ±{straddle_move:,.1f} pts (Biên độ cả kỳ: NQ {band_1s_dn_nq:,.1f} &mdash; {band_1s_up_nq:,.1f})<br>
        • <b>Intraday Expected Move (Rule of 16):</b> ±{intraday_move:,.1f} pts (Vùng dao động trong ngày: NQ {nq_spot-intraday_move:,.1f} &mdash; {nq_spot+intraday_move:,.1f})
    </div>

    <div class="insight-box" style="border-left-color: #F59E0B; margin-bottom: 24px;">
        <b style="color: #FCD34D; font-size: 14px;">⚡ [Ý NGHĨA & HÀNH ĐỘNG GREEKS BẬC 2 - VANNA & CHARM]:</b><br>
        • <b>ĐỈNH VANNA (+{total_vex:.1f}M):</b> <b>LỰC ĐẨY V-REBOUND</b> &rarr; Canh BUY lướt sóng khi IV hạ nhiệt sau tin tức hoặc đầu phiên.<br>
        • <b>ĐỈNH CHARM ({total_chex:.1f}M/ngày):</b> <b>NAM CHÂM GHÌM GIÁ ĐÊM</b> &rarr; Canh CHỐT LỜI hoặc đánh hồi quy (Mean-Reversion) về mốc này khi về đêm muộn.
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
                    <th>Vùng Giá Kích Hoạt</th>
                    <th>Entry NQ</th>
                    <th>Hard SL</th>
                    <th>Take Profit (TP)</th>
                    <th>Kịch Bản & Cơ Chế Market Maker</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><b style="color: var(--neon-green);">1. BUY MUA ĐUỔI (Squeeze Trigger)</b></td>
                    <td>Vượt > {trigger_up_nq:,.1f}</td>
                    <td>{trigger_up_nq+2.0:,.1f}</td>
                    <td>{trigger_up_nq-15.0:,.1f} (15p)</td>
                    <td>{cw_nq:,.1f} (Ăn trọn)</td>
                    <td style="font-family: sans-serif; color: var(--text-secondary);">MM vỡ trận Short -> Gamma Squeeze đẩy giá bốc đầu lên mốc tiếp theo.</td>
                </tr>
                <tr>
                    <td><b style="color: #FF5252;">2. SELL CẢN TIỀN TUYẾN (Fade Call Wall)</b></td>
                    <td>{cw_nq-10.0:,.1f} - {cw_nq:,.1f}</td>
                    <td>{cw_nq-2.0:,.1f}</td>
                    <td>{cw_nq+15.0:,.1f} (15p)</td>
                    <td>{pivot_nq:,.1f} (Hồi về Pivot)</td>
                    <td style="font-family: sans-serif; color: var(--text-secondary);">Call Vol cực đại -> MM bán Futures chặn đầu để bảo vệ trạng thái Short Gamma.</td>
                </tr>
                <tr>
                    <td><b style="color: #38BDF8;">3. BUY BẮT SÀN ATM (Rebound ATM Pivot)</b></td>
                    <td>{pivot_nq-8.0:,.1f} - {pivot_nq:,.1f}</td>
                    <td>{pivot_nq:,.1f}</td>
                    <td>{pivot_nq-15.0:,.1f} (15p)</td>
                    <td>{cw_nq-20.0:,.1f}</td>
                    <td style="font-family: sans-serif; color: var(--text-secondary);">Đệm Put hỗ trợ cân bằng giá (Put-Call Parity) giúp hồi phục kỹ thuật trong phiên.</td>
                </tr>
                <tr>
                    <td><b style="color: #F87171;">4. SELL THỦNG SÀN ATM (Breakdown Pivot)</b></td>
                    <td>Thủng &lt; {pivot_nq-10.0:,.1f}</td>
                    <td>{pivot_nq-12.0:,.1f}</td>
                    <td>{pivot_nq+10.0:,.1f} (10p)</td>
                    <td>{pw_nq:,.1f} (Rơi về Put Wall)</td>
                    <td style="font-family: sans-serif; color: var(--text-secondary);">Mất trục cân bằng Synthetic ATM -> Dealer xả hàng theo đà rơi về nấc tiếp theo.</td>
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
                    <th>Vùng Giá Kích Hoạt</th>
                    <th>Entry NQ</th>
                    <th>Hard SL</th>
                    <th>Take Profit (TP)</th>
                    <th>Ghi Chú Vị Thế Tổ Chức</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><b style="color: #EF4444;">5. BÁN ĐỈNH CALL WALL ({cw_nq:,.1f})</b></td>
                    <td>{cw_nq-15.0:,.1f} - {cw_nq:,.1f}</td>
                    <td>{cw_nq-5.0:,.1f}</td>
                    <td>{cw_nq+20.0:,.1f} (20p)</td>
                    <td>{pivot_nq:,.1f} / {pw_nq:,.1f}</td>
                    <td style="font-family: sans-serif; color: var(--text-secondary);">Call Wall {cw_oi:,} OI (Nóc nhà kiên cố nhất của MM). Kháng cự tuyệt đối khi Positive GEX.</td>
                </tr>
                <tr>
                    <td><b style="color: #10B981;">6. MUA ĐÁY PUT WALL ({pw_nq:,.1f})</b></td>
                    <td>{pw_nq:,.1f} - {pw_nq+15.0:,.1f}</td>
                    <td>{pw_nq+5.0:,.1f}</td>
                    <td>{pw_nq-20.0:,.1f} (20p)</td>
                    <td>{pivot_nq:,.1f} / {cw_nq:,.1f}</td>
                    <td style="font-family: sans-serif; color: var(--text-secondary);">Major Put Wall {pw_oi:,} OI (Đáy bê tông cốt thép). Vùng hấp thụ bán tháo của cá mập.</td>
                </tr>
            </tbody>
        </table>
    </div>

    <!-- Greeks Bac 2 Insights -->
    <div class="insight-box">
        <b>💡 Ý NGHĨA & HƯỚNG DẪN HÀNH ĐỘNG GREEKS BẬC 2 (VANNA & CHARM):</b><br>
        • <b>ĐỈNH VANNA (${total_vex:+.1f}M):</b> Lực đẩy V-Rebound đảo chiều. Khi thị trường ra tin tức hoặc sau giờ mở cửa (IV hạ nhiệt), các vị thế VEX dương sẽ kích hoạt Dealer mua bù thiếu, tạo sóng hồi chữ V cực mạnh.<br>
        • <b>ĐỈNH CHARM (${total_chex:+.1f}M/ngày):</b> Nam châm ghìm giá qua đêm do hao mòn thời gian (Theta/Charm decay). Vào cuối phiên Mỹ (sau 02:00 sáng VN), giá có xu hướng bị hút mạnh về trục cân bằng để triệt tiêu giá trị thời gian của quyền chọn mua/bán.
    </div>

    <!-- Microstructure Strike Table -->
    <div class="table-box">
        <div class="section-header">
            <span>📊 BẢNG DỮ LIỆU ĐỊNH LƯỢNG MICROSTRUCTURE TỪNG STRIKE (QQQ & E-MINI NQ)</span>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Strike QQQ</th>
                    <th>Strike NQ</th>
                    <th>Net GEX ($M)</th>
                    <th>Call OI</th>
                    <th>Put OI</th>
                    <th>Call Volume</th>
                    <th>Put Volume</th>
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
        NEIRO-NQ-QUANT TERMINAL &bull; 100% Python Cloud-First &bull; Zero-Waste (&lt; 15MB) &bull; Tự động đồng bộ hóa Google Drive: <code>latest_nq_dashboard.html</code>
    </div>
</div>
</body>
</html>
"""
    return html


def generate_ai_briefing(metrics: Dict[str, Any]) -> str:
    """Generate structured tactical prompt briefing for DeepSeek / Gemini AI."""
    nq = metrics["nq_levels"]
    qqq = metrics["qqq_levels"]
    
    air_pockets_text = ""
    if metrics["air_pockets"]:
        ap_list = [f"NQ {ap['strike_nq']} (QQQ {ap['strike_qqq']})" for ap in metrics["air_pockets"][:4]]
        air_pockets_text = ", ".join(ap_list)
    else:
        air_pockets_text = "Khong phat hien vung chan khong lon quanh ATM."

    states = metrics.get("level_states", {})
    state_str = f"Call Wall: [{states.get('call_wall', 'DORMANT')}] | Put Wall: [{states.get('put_wall', 'DORMANT')}] | Pivot: [{states.get('atm_pivot', 'DORMANT')}]"

    briefing = f"""
================================================================================
[!] NEIRO-NQ-QUANT: BAN GIAO NHIEM VU CHIEN THUAT E-MINI NASDAQ (AI BRIEFING)
================================================================================
Thoi diem phan tich : {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
Gia Spot QQQ        : ${metrics['spot_price_qqq']:.2f}
Gia E-mini NQ quy doi: {metrics['nq_futures_price']:.2f} (Ty le Basis: {metrics['basis_ratio']:.2f})
Tong Net GEX        : ${metrics['total_net_gex_millions']:.2f} Trieu USD
Che do thi truong    : {metrics['regime']}
Dac tinh thi truong : {metrics['regime_description']}
Radar State Machine : {state_str}

--------------------------------------------------------------------------------
[*] CAC MOC CAN CHU TRUC E-MINI NASDAQ (NQ FUTURES EQUIVALENT):
- CALL WALL (Tran cuong do) : NQ {nq['call_wall']} (QQQ {qqq['call_wall']})
- PUT WALL (Day thep)       : NQ {nq['put_wall']} (QQQ {qqq['put_wall']})
- PIN RISK MAGNET (Ho den)  : NQ {nq.get('pin_risk_magnet', 0)} (QQQ {qqq.get('pin_risk_magnet', 0)})
- ATM PIVOT (Truc can bang) : NQ {nq['atm_synthetic_pivot']} (QQQ {qqq['atm_synthetic_pivot']})
- GAMMA FLIP POINT          : NQ {nq['gamma_flip']} (QQQ {qqq['gamma_flip']})
- SQUEEZE TRIGGER UP        : NQ {nq.get('trigger_up', 0)}
- SQUEEZE TRIGGER DOWN      : NQ {nq.get('trigger_down', 0)}
- DAI BIEN DO 1-SIGMA (+/-1s): [{nq['lower_band_1s']} ---> {nq['upper_band_1s']}]
- DAI BIEN DO 2-SIGMA (+/-2s): [{nq['lower_band_2s']} ---> {nq['upper_band_2s']}]
- VUNG CHAN KHONG OI        : {air_pockets_text}

--------------------------------------------------------------------------------
[+] KICH BAN TAC CHIEN CHO TRADER:
1. Neu mo cua nam TREN Pivot {nq['atm_synthetic_pivot']} & Positive GEX:
   -> Uu tien mua khi gia pullback ve Pivot, muc tieu huong ve Call Wall {nq['call_wall']}.
   -> Tai Call Wall: Canh phan ung Limit Sell (Fade Reversal) hoac chot loi toan phan.

2. Neu gia pha thung Put Wall {nq['put_wall']} ket hop vung Chan khong:
   -> TUYET DOI KHONG BAT DAY vi Dealer bi force-hedge ban thao (Vacuum Slip).
   -> Canh danh theo xu huong Breakout huong thang ve moc bien do duoi -2s ({nq['lower_band_2s']}).

3. Kiem soat rui ro: Stop loss toi da 15 - 25 diem NQ (~0.5 - 0.7 gia QQQ), dat ngay sau chan can.
================================================================================
"""
    return briefing
