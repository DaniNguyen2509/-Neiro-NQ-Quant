"""
Cloud Parquet Storage Manager for Neiro-NQ-Quant.
Implements Google Drive / Local Partitioned Parquet storage and DuckDB Serverless query integration.
Zero-Waste Compliant (< 15MB local machine footprint).
"""
import os
import sys
import glob
import datetime
import pandas as pd
from typing import Optional, List, Dict, Any

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False


class ParquetStorageManager:
    """Manages writing and querying partitioned Apache Parquet snapshots."""

    def __init__(self, base_dir: Optional[str] = None):
        # Auto detect Google Colab environment
        self.is_colab = os.path.exists('/content')
        
        if base_dir:
            self.base_dir = base_dir
        elif self.is_colab and os.path.exists('/content/drive/MyDrive'):
            self.base_dir = '/content/drive/MyDrive/Neiro-NQ/data'
        elif os.path.exists(r'H:\My Drive\Neiro-NQ'):
            self.base_dir = r'H:\My Drive\Neiro-NQ\data'
        else:
            # Fallback to local cache within repo or temp
            self.base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'cache')
            
        os.makedirs(self.base_dir, exist_ok=True)

    def save_snapshot(
        self,
        df: pd.DataFrame,
        symbol: str = "QQQ",
        timestamp: Optional[datetime.datetime] = None
    ) -> str:
        """
        Save DataFrame snapshot into partitioned Parquet file.
        Partition scheme: base_dir/options/symbol=SYMBOL/year=YYYY/month=MM/date=YYYY-MM-DD/snapshot_HHMMSS.parquet
        """
        if df.empty:
            raise ValueError("Cannot save empty DataFrame to Parquet storage.")
            
        now = timestamp or datetime.datetime.now(datetime.timezone.utc)
        year_str = now.strftime("%Y")
        month_str = now.strftime("%m")
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H%M%S")
        
        partition_dir = os.path.join(
            self.base_dir,
            "options",
            f"symbol={symbol.upper()}",
            f"year={year_str}",
            f"month={month_str}",
            f"date={date_str}"
        )
        os.makedirs(partition_dir, exist_ok=True)
        
        file_path = os.path.join(partition_dir, f"snapshot_{time_str}.parquet")
        
        # Save with Snappy compression for maximum space efficiency
        df.to_parquet(file_path, engine="pyarrow", compression="snappy", index=False)
        return file_path

    def load_latest_snapshot(self, symbol: str = "QQQ") -> Optional[pd.DataFrame]:
        """Find and load the most recent Parquet snapshot for given symbol."""
        search_pattern = os.path.join(
            self.base_dir, "options", f"symbol={symbol.upper()}", "**", "*.parquet"
        )
        files = glob.glob(search_pattern, recursive=True)
        if not files:
            return None
            
        latest_file = max(files, key=os.path.getmtime)
        return pd.read_parquet(latest_file)

    def query_with_duckdb(self, sql_query: str) -> Optional[pd.DataFrame]:
        """Execute serverless SQL query across all stored Parquet files using DuckDB."""
        if not DUCKDB_AVAILABLE:
            print("[StorageManager] DuckDB is not installed, skipping SQL query.")
            return None
            
        con = duckdb.connect(database=":memory:")
        parquet_glob = os.path.join(self.base_dir, "options", "**", "*.parquet").replace('\\', '/')
        
        # Replace template table name with glob pattern
        resolved_sql = sql_query.replace("options_table", f"read_parquet('{parquet_glob}')")
        return con.execute(resolved_sql).df()

    def cleanup_old_local_cache(self, keep_last_n: int = 5) -> int:
        """
        Zero-Waste Mandate: Clean old scratch/cache files on local machine.
        Keeps only the most recent N files.
        """
        search_pattern = os.path.join(self.base_dir, "**", "*.parquet")
        files = glob.glob(search_pattern, recursive=True)
        if len(files) <= keep_last_n:
            return 0
            
        files_sorted = sorted(files, key=os.path.getmtime)
        files_to_remove = files_sorted if keep_last_n == 0 else files_sorted[:-keep_last_n]
        removed_count = 0
        for f in files_to_remove:
            try:
                os.remove(f)
                removed_count += 1
            except Exception:
                pass
        return removed_count
