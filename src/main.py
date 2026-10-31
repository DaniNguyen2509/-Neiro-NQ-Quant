"""
Neiro-NQ-Quant: Main Execution Pipeline.
Collects Nasdaq Options (via Barchart Scraper or Yahoo Finance), computes Black-76 Greeks & GEX matrix,
evaluates Level State Machine, saves Parquet/CSV, and renders Interactive Dark Terminal Dashboard.
100% Cloud-Native, Zero-Waste & ASCII/UTF-8 Compliant.
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
from src.quant_engine.engine import process_options_chain_black76
from src.dashboard.visualizer import build_tactical_dashboard, generate_ai_briefing
from src.hud.html_dashboard import build_and_export_dashboard


def run_pipeline(
    symbol: str = "QQQ",
    futures_symbol: str = "NQ=F",
    dual_frame: bool = False,
    export_html: bool = True,
    output_html: str = "exports/latest_nq_dashboard.html",
    output_json: str = "exports/nq_tactical_levels.json",
    basis: float = 0.0,
    input_csv: Optional[str] = None,
    multiplier: float = 20.0,
):
    print("=" * 80)
    print(f"[*] [Neiro-NQ-Quant] Starting E-mini Nasdaq Quant Pipeline ({symbol} -> {futures_symbol})")
    print("=" * 80)
    
    # 1. Fast & Free Black-76 Quant Pipeline via yfinance (Default)
    if not dual_frame:
        print(f"[*] Step 1: Processing Live Black-76 Quant Matrix via yfinance (Basis: {basis:+0.1f}, Multiplier: {multiplier})...")
        build_and_export_dashboard(
            csv_path=input_csv or "data/options_prices_NQZ26.csv",
            output_paths=[output_html, "exports/index.html"],
            basis=basis,
            multiplier=multiplier,
            source="csv" if input_csv else "yfinance",
        )
        print(f"[+] Step 2: Tactical HTML Dashboard published successfully.")
        print("=" * 80)
        print("[DONE] Cloud Pipeline completed successfully!")
        print("=" * 80)
        return


    # Standard YFinance / Multi-frame workflow
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
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
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
        export_dir = os.path.dirname(os.path.abspath(output_html))
        index_path = os.path.join(export_dir, "index.html")
        try:
            import shutil
            shutil.copy(output_html, index_path)
            print(f"[+] Created web root index: {index_path}")
        except Exception as e:
            print(f"[!] Warning: Could not create index.html: {e}")

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
    parser.add_argument("--input-csv", default=None, help="Path to pre-scraped options CSV")
    parser.add_argument("--basis", type=float, default=0.0, help="Spot MT5 Basis offset (Spot_MT5 = Spot_Futures - basis)")
    parser.add_argument("--multiplier", type=float, default=20.0, help="Contract multiplier (20 for NQ, 2 for MNQ)")
    parser.add_argument("--loop", type=int, default=0, help="Sync loop interval in seconds (e.g. 300 for 5 mins). Default 0 (run once)")
    
    args = parser.parse_args()
    
    if args.loop > 0:
        import time
        print(f"[*] [Loop Mode] Auto-synchronizing every {args.loop}s ({args.loop/60:.1f} mins). Press Ctrl+C to stop.")
        while True:
            try:
                run_pipeline(
                    symbol=args.symbol,
                    futures_symbol=args.futures,
                    dual_frame=args.dual_frame,
                    export_html=args.export_html,
                    output_html=args.output_html,
                    output_json=args.output_json,
                    basis=args.basis,
                    input_csv=args.input_csv,
                    multiplier=args.multiplier,
                )
                next_time = (datetime.datetime.now() + datetime.timedelta(seconds=args.loop)).strftime("%H:%M:%S")
                print(f"[*] Sleeping {args.loop}s... Next sync at {next_time}\n")
                time.sleep(args.loop)
            except KeyboardInterrupt:
                print("\n[!] Auto-sync stopped by user.")
                break
            except Exception as e:
                print(f"[!] Warning in loop execution ({e}). Retrying in {args.loop}s...")
                time.sleep(args.loop)
    else:
        run_pipeline(
            symbol=args.symbol,
            futures_symbol=args.futures,
            dual_frame=args.dual_frame,
            export_html=args.export_html,
            output_html=args.output_html,
            output_json=args.output_json,
            basis=args.basis,
            input_csv=args.input_csv,
            multiplier=args.multiplier,
        )

