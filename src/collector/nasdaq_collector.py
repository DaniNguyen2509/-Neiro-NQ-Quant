"""
Nasdaq Options Collector (QQQ / NDX / NQ Futures).
Fetches options chains, standardizes strikes, calculates Greeks, and maps to E-mini NQ equivalents.
Supports Dual-Frame analysis (0DTE/Weekly front frame + Monthly institutional frame).
Includes fault-tolerant embedded benchmark data for offline and zero-crash execution.
"""
import datetime
import math
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple

from src.collector.base import BaseCollector
from src.collector.greeks import vectorized_black_scholes_greeks, estimate_iv_brent


def calculate_dte(expiration_date_str: str) -> float:
    """Calculate fractional days to expiration (assuming 16:00 ET settlement)."""
    try:
        exp_date = datetime.datetime.strptime(str(expiration_date_str)[:10], "%Y-%m-%d").date()
        today = datetime.date.today()
        diff_days = (exp_date - today).days
        if diff_days <= 0:
            return 0.35  # Intraday 0DTE (~8.5 trading hours remaining)
        return float(diff_days)
    except Exception:
        return 1.0


class NasdaqCollector(BaseCollector):
    """Collector specialized for E-mini Nasdaq & QQQ Options with Dual-Frame support."""

    def __init__(
        self,
        symbol: str = "QQQ",
        futures_symbol: str = "NQ=F",
        risk_free_rate: float = 0.045,
        timeout: int = 20
    ):
        super().__init__(symbol=symbol, timeout=timeout)
        self.futures_symbol = futures_symbol
        self.risk_free_rate = risk_free_rate

    def get_available_expirations(self) -> List[str]:
        """Fetch list of available option expirations."""
        try:
            import yfinance as yf
            tk = yf.Ticker(self.symbol)
            expirations = list(tk.options)
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            valid = [e for e in expirations if e >= today_str]
            if valid:
                return sorted(valid)
            elif expirations:
                return sorted(expirations)
        except Exception as e:
            print(f"[NasdaqCollector] Warning: Could not fetch online expirations ({e})")
            
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        next_month = (datetime.date.today() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        return [today_str, next_month]

    def get_underlying_prices(self) -> Dict[str, float]:
        """Fetch current prices for underlying ETF and NQ futures, then calculate basis."""
        spot_price = 500.0
        futures_price = 20500.0
        
        try:
            import yfinance as yf
            # 1. Fetch Spot / ETF Price
            tk_spot = yf.Ticker(self.symbol)
            fast_info = getattr(tk_spot, "fast_info", None)
            if fast_info and "lastPrice" in fast_info:
                spot_price = float(fast_info["lastPrice"])
            else:
                hist = tk_spot.history(period="1d")
                if not hist.empty:
                    spot_price = float(hist["Close"].iloc[-1])
                    
            # 2. Fetch Futures Price (NQ=F)
            tk_fut = yf.Ticker(self.futures_symbol)
            fast_fut = getattr(tk_fut, "fast_info", None)
            if fast_fut and "lastPrice" in fast_fut:
                futures_price = float(fast_fut["lastPrice"])
            else:
                hist_fut = tk_fut.history(period="1d")
                if not hist_fut.empty:
                    futures_price = float(hist_fut["Close"].iloc[-1])

            # 3. Fetch Cash Index (^NDX) to auto-calculate MT5 CFD basis offset
            ndx_price = futures_price - 149.0
            try:
                tk_ndx = yf.Ticker("^NDX")
                fast_ndx = getattr(tk_ndx, "fast_info", None)
                if fast_ndx and "lastPrice" in fast_ndx:
                    ndx_price = float(fast_ndx["lastPrice"])
                else:
                    hist_ndx = tk_ndx.history(period="1d")
                    if not hist_ndx.empty:
                        ndx_price = float(hist_ndx["Close"].iloc[-1])
            except Exception:
                pass

            # 4. Fetch 13-Week Treasury Bill Yield (^IRX) for dynamic risk-free rate r
            r_rate = 0.0397
            try:
                tk_irx = yf.Ticker("^IRX")
                fast_irx = getattr(tk_irx, "fast_info", None)
                if fast_irx and "lastPrice" in fast_irx:
                    r_rate = float(fast_irx["lastPrice"]) / 100.0
                else:
                    hist_irx = tk_irx.history(period="1d")
                    if not hist_irx.empty:
                        r_rate = float(hist_irx["Close"].iloc[-1]) / 100.0
            except Exception:
                pass
        except Exception as e:
            print(f"[NasdaqCollector] Price fetch fallback used ({e})")

        basis_ratio = futures_price / max(1.0, spot_price)
        auto_basis_offset = max(0.0, futures_price - ndx_price)
        return {
            "underlying": float(spot_price),
            "futures": float(futures_price),
            "ndx": float(ndx_price),
            "basis": float(basis_ratio),
            "basis_offset": float(round(auto_basis_offset, 2)),
            "r_rate": float(round(r_rate, 4)),
        }

    def fetch_options_chain(self, expiration_date: Optional[str] = None) -> pd.DataFrame:
        """
        Fetch options chain for QQQ, compute Greeks and E-mini NQ equivalents.
        If online fetch fails or outside trading hours, safely fallbacks to embedded data.
        """
        prices = self.get_underlying_prices()
        spot = prices["underlying"]
        futures = prices["futures"]
        basis = prices["basis"]
        
        df_chain = pd.DataFrame()
        target_expiry = expiration_date
        
        try:
            import yfinance as yf
            tk = yf.Ticker(self.symbol)
            all_expiries = list(tk.options)
            
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            valid_expiries = [e for e in all_expiries if e >= today_str] if all_expiries else []
            if not target_expiry and valid_expiries:
                target_expiry = valid_expiries[0]
            elif not target_expiry and all_expiries:
                target_expiry = all_expiries[0]
            elif not target_expiry:
                target_expiry = today_str
                
            if all_expiries and target_expiry in all_expiries:
                chain = tk.option_chain(target_expiry)
                calls = chain.calls
                puts = chain.puts
                
                merged = pd.merge(
                    calls, puts, on='strike', suffixes=('_call', '_put'), how='outer'
                ).sort_values('strike').reset_index(drop=True)
                
                rows = []
                for _, r in merged.iterrows():
                    stk = float(r['strike'])
                    c_bid = float(r.get('bid_call', 0.0) or 0.0)
                    c_ask = float(r.get('ask_call', 0.0) or 0.0)
                    c_mid = 0.5 * (c_bid + c_ask) if (c_bid + c_ask) > 0 else float(r.get('lastPrice_call', 0.0) or 0.0)
                    c_vol = float(r.get('volume_call', 0.0) or 0.0)
                    c_oi = float(r.get('openInterest_call', 0.0) or 0.0)
                    c_iv = float(r.get('impliedVolatility_call', 0.18) or 0.18)
                    
                    p_bid = float(r.get('bid_put', 0.0) or 0.0)
                    p_ask = float(r.get('ask_put', 0.0) or 0.0)
                    p_mid = 0.5 * (p_bid + p_ask) if (p_bid + p_ask) > 0 else float(r.get('lastPrice_put', 0.0) or 0.0)
                    p_vol = float(r.get('volume_put', 0.0) or 0.0)
                    p_oi = float(r.get('openInterest_put', 0.0) or 0.0)
                    p_iv = float(r.get('impliedVolatility_put', 0.18) or 0.18)
                    
                    rows.append({
                        'strike': stk,
                        'strikeNQ': round(stk * basis, 2),
                        'callBid': c_bid, 'callAsk': c_ask, 'callMid': c_mid,
                        'callVolume': c_vol, 'callOpenInterest': c_oi, 'callIV': c_iv,
                        'putBid': p_bid, 'putAsk': p_ask, 'putMid': p_mid,
                        'putVolume': p_vol, 'putOpenInterest': p_oi, 'putIV': p_iv,
                        'expirationDate': target_expiry
                    })
                    
                df_chain = pd.DataFrame(rows)
        except Exception as e:
            print(f"[NasdaqCollector] Online chain fetch failed ({e}), loading benchmark fallback.")

        if df_chain.empty or len(df_chain) < 5:
            df_chain = self._generate_benchmark_chain(spot, basis)
            
        dte_days = calculate_dte(target_expiry or datetime.date.today().strftime("%Y-%m-%d"))
        df_chain = self._enrich_quant_metrics(df_chain, spot, dte_days=dte_days)
        return df_chain

    def fetch_standardized_nq_chain(self, expiration_date: Optional[str] = None) -> Tuple[pd.DataFrame, Dict[str, float]]:
        """
        Fetch QQQ options chain via yfinance and map cleanly to E-mini NQ strikes.
        Returns (standardized DataFrame ready for Black-76 quant engine, prices dict).
        Fast, zero-cost, no browser, and bypasses Cloudflare entirely.
        """
        prices = self.get_underlying_prices()
        spot = prices["underlying"]
        futures = prices["futures"]
        basis = prices["basis"]

        df_raw = self.fetch_options_chain(expiration_date=expiration_date)
        
        # Standardize for Black-76 quant engine: strike is mapped to NQ index points
        def safe_f(v, default=0.0) -> float:
            if v is None or pd.isna(v):
                return default
            try:
                val = float(v)
                return default if (math.isnan(val) or math.isinf(val)) else val
            except Exception:
                return default

        def safe_i(v, default=0) -> int:
            if v is None or pd.isna(v):
                return default
            try:
                val = float(v)
                return default if (math.isnan(val) or math.isinf(val)) else int(val)
            except Exception:
                return default

        rows = []
        for _, r in df_raw.iterrows():
            stk_q = safe_f(r.get('strike'), 500.0)
            stk_nq = round(stk_q * basis, 0)
            # Scale option premiums proportionally from QQQ dollars to NQ futures index points
            c_bid = round(safe_f(r.get('callBid')) * basis, 2)
            c_ask = round(safe_f(r.get('callAsk')) * basis, 2)
            c_mid = round(safe_f(r.get('callMid')) * basis, 2)
            p_bid = round(safe_f(r.get('putBid')) * basis, 2)
            p_ask = round(safe_f(r.get('putAsk')) * basis, 2)
            p_mid = round(safe_f(r.get('putMid')) * basis, 2)
            rows.append({
                "strike": stk_nq,
                "strikeQQQ": stk_q,
                "callBid": c_bid,
                "callAsk": c_ask,
                "callMid": c_mid,
                "callLatest": c_mid,
                "callVolume": safe_i(r.get('callVolume')),
                "callOpenInterest": safe_i(r.get('callOpenInterest')),
                "callGamma": safe_f(r.get('callGamma'), 0.0003),
                "callIV": safe_f(r.get('callIV'), 0.18),
                "putBid": p_bid,
                "putAsk": p_ask,
                "putMid": p_mid,
                "putLatest": p_mid,
                "putVolume": safe_i(r.get('putVolume')),
                "putOpenInterest": safe_i(r.get('putOpenInterest')),
                "putGamma": safe_f(r.get('putGamma'), 0.0003),
                "putIV": safe_f(r.get('putIV'), 0.18),
                "expirationDate": r.get('expirationDate', datetime.date.today().strftime("%Y-%m-%d")),
            })

        df_nq = pd.DataFrame(rows).sort_values("strike").drop_duplicates(subset=["strike"]).reset_index(drop=True)
        return df_nq, prices

    def fetch_dual_frame_chains(self) -> Dict[str, pd.DataFrame]:
        """
        Fetch both Front-Frame (0DTE/Weekly) and Institutional-Frame (Monthly).
        Returns: {'front': DataFrame, 'institutional': DataFrame}
        """
        expiries = self.get_available_expirations()
        front_exp = expiries[0] if expiries else None
        inst_exp = expiries[min(len(expiries) - 1, 4)] if len(expiries) > 1 else front_exp
        
        df_front = self.fetch_options_chain(expiration_date=front_exp)
        if inst_exp and inst_exp != front_exp:
            df_inst = self.fetch_options_chain(expiration_date=inst_exp)
        else:
            df_inst = df_front.copy()
            
        return {
            "front": df_front,
            "institutional": df_inst
        }

    def fetch_real_candles(
        self,
        timeframes: Optional[List[str]] = None,
        limit: int = 120
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch real historical OHLCV data for NQ=F across timeframes."""
        if timeframes is None:
            timeframes = ["1m", "5m", "15m", "1h", "1d"]
        import yfinance as yf
        result = {}
        tk = yf.Ticker(self.futures_symbol)
        period_map = {
            "1m": "2d",
            "5m": "5d",
            "15m": "5d",
            "1h": "1mo",
            "1d": "3mo"
        }
        for tf in timeframes:
            try:
                per = period_map.get(tf, "5d")
                hist = tk.history(period=per, interval=tf)
                if not hist.empty:
                    bars = []
                    tail_df = hist.tail(limit)
                    for idx, row in tail_df.iterrows():
                        t_sec = int(idx.timestamp())
                        bars.append({
                            "time": t_sec,
                            "open": round(float(row["Open"]), 2),
                            "high": round(float(row["High"]), 2),
                            "low": round(float(row["Low"]), 2),
                            "close": round(float(row["Close"]), 2),
                            "volume": int(row["Volume"]) if ("Volume" in row and not pd.isna(row["Volume"])) else 0
                        })
                    if bars:
                        result[tf] = bars
            except Exception as e:
                print(f"[NasdaqCollector] Warning: Could not fetch real candles for {tf}: {e}")
        return result

    def _enrich_quant_metrics(self, df: pd.DataFrame, spot: float, dte_days: float = 1.0) -> pd.DataFrame:
        """Vectorized enrichment: calculates Greeks (Delta, Gamma, Vega, Vanna, Charm), GEX, DEX, VEX, CHEX."""
        t_years = max(float(dte_days) / 365.0, 1.0 / (365.0 * 1440.0))
        r = self.risk_free_rate
        mult = 100.0
        scale = (spot ** 2) * 0.01 / 1e6
        
        strikes = df['strike'].values
        c_ivs = df['callIV'].values
        p_ivs = df['putIV'].values
        
        # Calls Greeks (price, delta, gamma, vega, vanna, charm)
        _, c_delta, c_gamma, c_vega, c_vanna, c_charm = vectorized_black_scholes_greeks(
            spot, strikes, t_years, r, c_ivs, is_call=True
        )
        # Puts Greeks
        _, p_delta, p_gamma, p_vega, p_vanna, p_charm = vectorized_black_scholes_greeks(
            spot, strikes, t_years, r, p_ivs, is_call=False
        )
        
        df['callDelta'] = c_delta
        df['callGamma'] = c_gamma
        df['callVega'] = c_vega
        df['callVanna'] = c_vanna
        df['callCharm'] = c_charm
        
        df['putDelta'] = p_delta
        df['putGamma'] = p_gamma
        df['putVega'] = p_vega
        df['putVanna'] = p_vanna
        df['putCharm'] = p_charm
        
        # 1. GEX (Gamma Exposure in Millions of USD per 1% move)
        df['callGEX'] = df['callGamma'] * df['callOpenInterest'] * mult * scale
        df['putGEX'] = - (df['putGamma'] * df['putOpenInterest'] * mult * scale)
        df['netGEX'] = df['callGEX'] + df['putGEX']
        
        # 2. DEX (Delta Exposure in Millions of USD)
        df['callDEX'] = df['callDelta'] * df['callOpenInterest'] * mult * spot / 1e6
        df['putDEX'] = df['putDelta'] * df['putOpenInterest'] * mult * spot / 1e6
        df['netDEX'] = df['callDEX'] + df['putDEX']

        # 3. VEX (Vanna Exposure in Millions of USD per 1% IV change)
        df['callVEX'] = df['callVanna'] * df['callOpenInterest'] * mult * spot * 0.01 / 1e6
        df['putVEX'] = - (df['putVanna'] * df['putOpenInterest'] * mult * spot * 0.01 / 1e6)
        df['netVEX'] = df['callVEX'] + df['putVEX']

        # 4. CHEX (Charm Exposure in Millions of USD per day of time decay)
        df['callCHEX'] = (df['callCharm'] / 365.0) * df['callOpenInterest'] * mult * spot / 1e6
        df['putCHEX'] = - ((df['putCharm'] / 365.0) * df['putOpenInterest'] * mult * spot / 1e6)
        df['netCHEX'] = df['callCHEX'] + df['putCHEX']
        
        return df

    def _generate_benchmark_chain(self, spot: float, basis: float) -> pd.DataFrame:
        """Embedded high-fidelity benchmark QQQ options chain around spot price."""
        atm = round(spot / 5.0) * 5.0
        offsets = [-30, -25, -20, -15, -10, -8, -6, -4, -2, 0, 2, 4, 6, 8, 10, 15, 20, 25, 30]
        
        rows = []
        for off in offsets:
            stk = atm + off
            c_oi = max(50.0, 1800.0 - abs(off) * 45.0 + (500.0 if off == 10 else 0.0))
            p_oi = max(50.0, 2200.0 - abs(off) * 50.0 + (800.0 if off == -10 else 0.0))
            c_vol = c_oi * 0.4
            p_vol = p_oi * 0.35
            
            c_mid = max(0.1, spot - stk + 3.5) if stk <= spot else max(0.1, 4.0 - off * 0.2)
            p_mid = max(0.1, stk - spot + 3.5) if stk >= spot else max(0.1, 4.0 + off * 0.2)
            
            rows.append({
                'strike': float(stk),
                'strikeNQ': round(stk * basis, 2),
                'callBid': round(c_mid * 0.98, 2),
                'callAsk': round(c_mid * 1.02, 2),
                'callMid': round(c_mid, 2),
                'callVolume': round(c_vol, 0),
                'callOpenInterest': round(c_oi, 0),
                'callIV': 0.185,
                'putBid': round(p_mid * 0.98, 2),
                'putAsk': round(p_mid * 1.02, 2),
                'putMid': round(p_mid, 2),
                'putVolume': round(p_vol, 0),
                'putOpenInterest': round(p_oi, 0),
                'putIV': 0.190,
                'expirationDate': datetime.date.today().strftime("%Y-%m-%d")
            })
            
        return pd.DataFrame(rows)


def generate_benchmark_nq_chain(spot: float = 28500.0) -> pd.DataFrame:
    """Generate high-fidelity benchmark E-mini NQ options chain for offline / test execution."""
    atm = round(spot / 50.0) * 50.0
    offsets = [
        -1500, -1250, -1000, -800, -600, -500, -400, -300, -250, -200, -150, -100, -50,
        0, 50, 100, 150, 200, 250, 300, 400, 500, 600, 800, 1000, 1250, 1500
    ]
    rows = []
    for off in offsets:
        stk = atm + off
        c_oi = max(100.0, 3800.0 - abs(off) * 1.8 + (1200.0 if off == 500 else 0.0))
        p_oi = max(100.0, 4200.0 - abs(off) * 1.9 + (1500.0 if off == -500 else 0.0))
        c_vol = round(c_oi * 0.35)
        p_vol = round(p_oi * 0.40)
        c_mid = max(5.0, spot - stk + 60.0) if stk <= spot else max(5.0, 75.0 - off * 0.08)
        p_mid = max(5.0, stk - spot + 60.0) if stk >= spot else max(5.0, 75.0 + off * 0.08)

        rows.append({
            "strike": float(stk),
            "callBid": round(c_mid * 0.98, 2),
            "callAsk": round(c_mid * 1.02, 2),
            "callMid": round(c_mid, 2),
            "callLatest": round(c_mid, 2),
            "callVolume": int(c_vol),
            "callOpenInterest": int(c_oi),
            "callGamma": 0.00032,
            "callIV": 0.185,
            "putBid": round(p_mid * 0.98, 2),
            "putAsk": round(p_mid * 1.02, 2),
            "putMid": round(p_mid, 2),
            "putLatest": round(p_mid, 2),
            "putVolume": int(p_vol),
            "putOpenInterest": int(p_oi),
            "putGamma": 0.00032,
            "putIV": 0.190,
        })
    return pd.DataFrame(rows)

