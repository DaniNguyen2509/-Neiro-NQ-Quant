"""
Integration tests for NasdaqCollector, StorageManager, and Microstructure Engine.
"""
import os
import shutil
import tempfile
import pytest
import pandas as pd
from src.collector.nasdaq_collector import NasdaqCollector
from src.collector.storage import ParquetStorageManager
from src.quant_engine.structure import calculate_microstructure_levels


def test_collector_and_storage_pipeline():
    """Test full cycle: Fetch -> Calculate Levels -> Save Parquet -> Reload."""
    collector = NasdaqCollector(symbol="QQQ", futures_symbol="NQ=F")
    
    # 1. Fetch
    df = collector.fetch_options_chain()
    assert not df.empty
    assert len(df) >= 5
    assert "strike" in df.columns
    assert "netGEX" in df.columns
    assert "strikeNQ" in df.columns
    assert "callVEX" in df.columns
    assert "callCHEX" in df.columns
    
    # 2. Levels
    prices = collector.get_underlying_prices()
    levels = calculate_microstructure_levels(
        df,
        spot_price=prices["underlying"],
        basis_ratio=prices["basis"]
    )
    assert "call_wall" in levels["nq_levels"]
    assert "put_wall" in levels["nq_levels"]
    assert "pin_risk_magnet" in levels["nq_levels"]
    assert "trigger_up" in levels["nq_levels"]
    assert "trigger_down" in levels["nq_levels"]
    assert "atm_synthetic_pivot" in levels["nq_levels"]
    assert levels["nq_levels"]["call_wall"] > 0
    assert levels["nq_levels"]["put_wall"] > 0
    
    # 3. Storage in temp directory
    temp_dir = tempfile.mkdtemp()
    try:
        storage = ParquetStorageManager(base_dir=temp_dir)
        saved_file = storage.save_snapshot(df, symbol="QQQ")
        assert os.path.exists(saved_file)
        assert saved_file.endswith(".parquet")
        
        # Reload
        reloaded = storage.load_latest_snapshot(symbol="QQQ")
        assert reloaded is not None
        assert len(reloaded) == len(df)
        
        # Test Zero-waste cleanup
        cleaned = storage.cleanup_old_local_cache(keep_last_n=0)
        assert cleaned >= 1
    finally:
        # Zero-waste cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_dual_frame_collection():
    """Verify that fetch_dual_frame_chains returns both front and institutional frames."""
    collector = NasdaqCollector(symbol="QQQ", futures_symbol="NQ=F")
    chains = collector.fetch_dual_frame_chains()
    assert "front" in chains
    assert "institutional" in chains
    assert not chains["front"].empty
    assert not chains["institutional"].empty
