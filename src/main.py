"""
Neiro-NQ-Quant: Main Execution Pipeline.
Collects Nasdaq Options, computes Greeks & GEX matrix, evaluates Level State Machine,
saves Parquet to Cloud/Local, and renders Interactive Dashboard.
Zero-Waste & ASCII Compliant.
"""
import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
import json
import datetime
import argparse
import pandas as pd
from typing import Optional, Dict, Any

from src.collector.nasdaq_collector import NasdaqCollector
from src.collector.storage import ParquetStorageManager
from src.quant_engine.structure import calculate_microstructure_levels
from src.quant_engine.state_machine import LevelStateMachine
from src.dashboard.visualizer import build_tactical_dashboard, generate_ai_briefing


def run_pipeline(
    symbol: str = "QQQ",
    futures_symbol: str = "NQ=F",
    dual_frame: bool = False,
    export_html: bool = True,
    output_html: str = "exports/latest_nq_dashboard.html",
    output_json: str = "exports/nq_tactical_levels.json"
):
    print("=" * 80)
    print(f"[*] [Neiro-NQ-Quant] Starting E-mini Nasdaq Quant Pipeline ({symbol} -> {futures_symbol})")
    print("=" * 80)
    
    # 1. Collector
    collector = NasdaqCollector(symbol=symbol, futures_symbol=futures_symbol)
    if dual_frame:
        print(f"[*] Step 1: Fetching Dual-Frame options chains (0DTE + Monthly)...")
        chains = collector.fetch_dual_frame_chains()
        df_chain = chains["front"]
        print(f"[+] Front frame: {len(df_chain)} strikes | Institutional frame: {len(chains['institutional'])} strikes.")
    else:
        print(f"[*] Step 1: Fetching options chain for {symbol}...")
        df_chain = collector.fetch_options_chain()
        print(f"[+] Loaded {len(df_chain)} strikes with Greeks & E-mini NQ equivalents.")
    
    # 2. Cloud Parquet Storage
    storage = ParquetStorageManager()
    saved_path = storage.save_snapshot(df_chain, symbol=symbol)
    print(f"[+] Step 2: Parquet snapshot saved to: {saved_path}")
    
    # 3. Quant Engine (3-Tier)
    print("[*] Step 3: Computing GEX, Walls, ATM Pivot, and Air Pockets...")
    prices = collector.get_underlying_prices()
    metrics = calculate_microstructure_levels(
        df_chain,
        spot_price=prices["underlying"],
        basis_ratio=prices["basis"]
    )
    print(f"[+] Market Regime: {metrics['regime']} (Total Net GEX: ${metrics['total_net_gex_millions']:.1f}M)")
    print(f"[+] Call Wall: NQ {metrics['nq_levels']['call_wall']} | Put Wall: NQ {metrics['nq_levels']['put_wall']}")
    print(f"[+] ATM Pivot: NQ {metrics['nq_levels']['atm_synthetic_pivot']}")
    
    # 4. Level State Machine Engine
    state_machine = LevelStateMachine()
    tactical_recs = state_machine.evaluate(
        current_nq_price=metrics["nq_futures_price"],
        metrics=metrics
    )
    print("\n--- LEVEL STATE MACHINE RADAR ---")
    for r in tactical_recs:
        print(f"[{r.state.value:18}] {r.level_name:20} -> NQ {r.level_price_nq:8.1f} | Action: {r.action:14} | SL: {r.stop_loss_nq:8.1f} | TP: {r.take_profit_nq:8.1f}")
    print("-" * 80)

    # 5. Tactical AI Briefing
    briefing = generate_ai_briefing(metrics)
    print(briefing)
    
    # 6. Export Hot Tactical JSON Feed
    os.makedirs(os.path.dirname(os.path.abspath(output_json)), exist_ok=True)
    json_feed = {
        "timestamp": str(pd.Timestamp.now(datetime.timezone.utc) if 'pd' in locals() else ""),
        "symbol": symbol,
        "futures_symbol": futures_symbol,
        "metrics": metrics,
        "tactical_recommendations": [
            {
                "level_name": r.level_name,
                "level_price_nq": r.level_price_nq,
                "state": r.state.value,
                "action": r.action,
                "entry_guide": r.entry_guide,
                "stop_loss_nq": r.stop_loss_nq,
                "take_profit_nq": r.take_profit_nq,
                "risk_warning": r.risk_warning
            }
            for r in tactical_recs
        ]
    }
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(json_feed, f, indent=2, default=str)
    print(f"[+] Exported hot JSON feed to: {output_json}")

    # 7. Interactive Dashboard
    if export_html:
        print("[*] Step 7: Generating Plotly Interactive Dashboard...")
        build_tactical_dashboard(df_chain, metrics, output_html_path=output_html)

    # 8. Mirror to Google Drive root if connected
    drive_root = None
    if os.path.exists(r"H:\My Drive\Neiro-NQ"):
        drive_root = r"H:\My Drive\Neiro-NQ"
    elif os.path.exists("/content/drive/MyDrive/Neiro-NQ"):
        drive_root = "/content/drive/MyDrive/Neiro-NQ"

    if drive_root:
        try:
            import shutil
            shutil.copy(output_json, os.path.join(drive_root, "nq_tactical_levels.json"))
            if export_html and os.path.exists(output_html):
                shutil.copy(output_html, os.path.join(drive_root, "latest_nq_dashboard.html"))
            print(f"[+] Synchronized dashboard & JSON to Google Drive: {drive_root}")
        except Exception as e:
            print(f"[!] Warning: Could not mirror to Drive root: {e}")
        
    print("=" * 80)
    print("[DONE] Pipeline completed successfully!")
    print("=" * 80)
    return metrics, df_chain


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Neiro-NQ-Quant Execution Pipeline")
    parser.add_argument("--symbol", default="QQQ", help="Underlying symbol (default: QQQ)")
    parser.add_argument("--futures", default="NQ=F", help="Futures reference symbol (default: NQ=F)")
    parser.add_argument("--dual-frame", action="store_true", default=False, help="Enable Dual-Frame collection (0DTE + Monthly)")
    parser.add_argument("--export-html", action="store_true", default=True, help="Export interactive HTML dashboard")
    parser.add_argument("--output-html", default="exports/latest_nq_dashboard.html", help="Path to output HTML file")
    parser.add_argument("--output-json", default="exports/nq_tactical_levels.json", help="Path to output JSON feed")
    
    args = parser.parse_args()
    run_pipeline(
        symbol=args.symbol,
        futures_symbol=args.futures,
        dual_frame=args.dual_frame,
        export_html=args.export_html,
        output_html=args.output_html,
        output_json=args.output_json
    )
