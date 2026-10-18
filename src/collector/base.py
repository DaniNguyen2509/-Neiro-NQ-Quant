"""
Abstract Base Collector for Neiro-NQ-Quant.
Defines standard contracts for all financial market data collectors.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import pandas as pd


class BaseCollector(ABC):
    """Abstract interface that all options data collectors must implement."""

    def __init__(self, symbol: str = "QQQ", timeout: int = 20):
        self.symbol = symbol.upper()
        self.timeout = timeout

    @abstractmethod
    def get_available_expirations(self) -> List[str]:
        """Return list of available expiration dates (format YYYY-MM-DD)."""
        pass

    @abstractmethod
    def fetch_options_chain(self, expiration_date: Optional[str] = None) -> pd.DataFrame:
        """
        Fetch full options chain for given expiration date.
        If expiration_date is None, automatically select the nearest (0DTE/1DTE).
        
        Returns DataFrame with standardized columns:
        ['strike', 'callBid', 'callAsk', 'callMid', 'callVolume', 'callOpenInterest',
         'callIV', 'callGamma', 'callDelta', 'putBid', 'putAsk', 'putMid', 
         'putVolume', 'putOpenInterest', 'putIV', 'putGamma', 'putDelta']
        """
        pass

    @abstractmethod
    def fetch_dual_frame_chains(self) -> Dict[str, pd.DataFrame]:
        """
        Fetch both Front-Frame (0DTE/Weekly) and Institutional-Frame (Monthly).
        Returns: {'front': DataFrame, 'institutional': DataFrame}
        """
        pass

    @abstractmethod
    def get_underlying_prices(self) -> Dict[str, float]:
        """
        Return current spot price and futures reference price.
        Returns: {'underlying': float, 'futures': float, 'basis': float}
        """
        pass

    def validate_chain(self, df: pd.DataFrame) -> bool:
        """Validate that the fetched options chain has required columns and non-empty rows."""
        required_cols = [
            'strike', 'callBid', 'callAsk', 'callVolume', 'callOpenInterest',
            'putBid', 'putAsk', 'putVolume', 'putOpenInterest'
        ]
        if df.empty:
            return False
        for col in required_cols:
            if col not in df.columns:
                return False
        return len(df) >= 3
