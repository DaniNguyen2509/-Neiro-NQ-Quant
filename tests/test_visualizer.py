"""
Tests for visualizer.py: 3-panel horizontal price ladder and standalone HTML report.
"""
import os
import tempfile
import pytest
import pandas as pd
from src.collector.nasdaq_collector import NasdaqCollector
from src.quant_engine.structure import calculate_microstructure_levels
from src.dashboard.visualizer import build_tactical_dashboard, generate_ai_briefing


def test_build_tactical_dashboard_and_html_export():
    collector = NasdaqCollector(symbol="QQQ", futures_symbol="NQ=F")
    df = collector.fetch_options_chain()
    prices = collector.get_underlying_prices()
    metrics = calculate_microstructure_levels(
        df,
        spot_price=prices["underlying"],
        basis_ratio=prices["basis"]
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        out_html = os.path.join(tmpdir, "test_dashboard.html")
        fig = build_tactical_dashboard(df, metrics, output_html_path=out_html)
        
        assert fig is not None
        assert os.path.exists(out_html)
        
        # Verify HTML content
        with open(out_html, "r", encoding="utf-8") as f:
            content = f.read()
            assert "NEIRO-NQ-QUANT" in content
            assert "Panel 1: Net GEX" in content
            assert "PHẦN 1: BẢNG TÁC CHIẾN LƯỚT SÓNG TRONG NGÀY" in content
            assert "PHẦN 2: BẢNG TÁC CHIẾN PHỤC KÍCH THÀNH TRÌ" in content
            assert "plotly-2.35.2.min.js" in content
            
    briefing = generate_ai_briefing(metrics)
    assert "AI BRIEFING" in briefing
    assert "CALL WALL" in briefing
