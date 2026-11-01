"""
Level State Machine Engine for E-mini Nasdaq.
Tracks real-time proximity and structural integrity of key price levels.
Directly implements Neiro-Quant 4-state transition architecture:
[DORMANT] -> [TRIGGERED / TESTING] -> [ABSORPTION_DEFENDED] vs [SLICING_RISK / SLICED_VACUUM]
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from enum import Enum


class LevelState(str, Enum):
    DORMANT = "DORMANT"
    TRIGGERED_TESTING = "TRIGGERED_TESTING"
    ABSORPTION_DEFENDED = "ABSORPTION_DEFENDED"
    SLICING_RISK = "SLICING_RISK"
    SLICED_VACUUM = "SLICED_VACUUM"


@dataclass
class TacticalRecommendation:
    level_name: str
    level_price_nq: float
    level_price_qqq: float
    state: LevelState
    action: str
    entry_guide: str
    stop_loss_nq: float
    take_profit_nq: float
    risk_warning: str


class LevelStateMachine:
    """Manages real-time state transitions and tactical trade recommendations for each level."""

    def __init__(
        self,
        proximity_threshold_nq: float = 15.0,
        breakout_threshold_nq: float = 12.0
    ):
        self.proximity_threshold = proximity_threshold_nq
        self.breakout_threshold = breakout_threshold_nq

    def evaluate(
        self,
        current_nq_price: float,
        metrics: Dict[str, Any]
    ) -> List[TacticalRecommendation]:
        """
        Evaluate all key structural levels against current market price and Net GEX regime.
        """
        recs = []
        nq_levels = metrics["nq_levels"]
        qqq_levels = metrics["qqq_levels"]
        regime = metrics["regime"]
        total_gex = metrics["total_net_gex_millions"]
        air_pockets = metrics.get("air_pockets", [])
        
        atm_pivot_nq = nq_levels["atm_synthetic_pivot"]
        
        levels_to_track = [
            ("CALL WALL #1", nq_levels["call_wall"], qqq_levels["call_wall"], "RESISTANCE"),
            ("PUT WALL #1", nq_levels["put_wall"], qqq_levels["put_wall"], "SUPPORT"),
            ("ATM SYNTHETIC PIVOT", nq_levels["atm_synthetic_pivot"], qqq_levels["atm_synthetic_pivot"], "EQUILIBRIUM"),
            ("PIN RISK MAGNET", nq_levels.get("pin_risk_magnet", 0), qqq_levels.get("pin_risk_magnet", 0), "MAGNET"),
            ("GAMMA FLIP POINT", nq_levels["gamma_flip"], qqq_levels["gamma_flip"], "REGIME_BOUNDARY"),
        ]
        
        # Check if any air pocket is nearby
        air_pocket_nq_strikes = [ap["strike_nq"] for ap in air_pockets]

        for name, price_nq, price_qqq, role in levels_to_track:
            if price_nq <= 0:
                continue
                
            dist = abs(current_nq_price - price_nq)
            has_air_pocket_behind = any(abs(price_nq - ap_nq) <= 25.0 for ap_nq in air_pocket_nq_strikes)
            
            # Determine State
            if role == "SUPPORT":
                default_sl = price_nq - 20.0
                default_tp = atm_pivot_nq if price_nq < atm_pivot_nq else price_nq + 50.0
            elif role == "RESISTANCE":
                default_sl = price_nq + 20.0
                default_tp = atm_pivot_nq if price_nq > atm_pivot_nq else price_nq - 50.0
            else:
                if current_nq_price >= price_nq:
                    default_sl = price_nq - 20.0
                    default_tp = nq_levels.get("call_wall", price_nq + 80.0)
                else:
                    default_sl = price_nq + 20.0
                    default_tp = nq_levels.get("put_wall", price_nq - 80.0)

            if dist > self.proximity_threshold:
                state = LevelState.DORMANT
                action = "MONITORING"
                entry_guide = f"Dung ngoai quan sat. Gia cach level {dist:.1f} diem NQ."
                sl = default_sl
                tp = default_tp
                warning = "Chua co phan ung vi mo."
                
            elif dist <= self.proximity_threshold and dist > 3.0:
                state = LevelState.TRIGGERED_TESTING
                action = "PREPARING"
                entry_guide = f"Gia dang tiep can vung dem ({dist:.1f} pts). Quan sat phan ung tai {price_nq:.1f}."
                sl = default_sl
                tp = default_tp
                warning = "Khong vao lenh Market non truoc khi co xac nhan nen."
                
            else:
                # Dist <= 3.0 pts (At the level)
                if total_gex > 0:
                    state = LevelState.ABSORPTION_DEFENDED
                    action = "FADE_REVERSAL"
                    if role == "RESISTANCE":
                        entry_guide = f"Canh Limit Sell khi nen rut chan duoi {price_nq:.1f}. Muc tieu ve Pivot {atm_pivot_nq:.1f}."
                        sl = price_nq + 15.0
                        tp = atm_pivot_nq
                        warning = "Dealer dang hap thu mua, nén chat bien do dao chieu."
                    else:
                        entry_guide = f"Canh Limit Buy khi nen rut chan tren {price_nq:.1f}. Muc tieu ve Pivot {atm_pivot_nq:.1f}."
                        sl = price_nq - 15.0
                        tp = atm_pivot_nq
                        warning = "Dealer dang hap thu ban, chan do thanh cong."
                else:
                    # Negative GEX
                    if has_air_pocket_behind:
                        state = LevelState.SLICED_VACUUM
                        action = "BREAKOUT_RUNNER"
                        entry_guide = f"DANH DUOI XU HUONG (Breakout) neu nen M5 dong xuyen qua {price_nq:.1f}."
                        sl = price_nq + 12.0 if role == "SUPPORT" else price_nq - 12.0
                        tp = price_nq - 80.0 if role == "SUPPORT" else price_nq + 80.0
                        warning = "NGUY HIEM: Phia sau la vung Chan khong thanh khoan. TUYET DOI KHONG BAT DAY!"
                    else:
                        state = LevelState.SLICING_RISK
                        action = "CAUTION"
                        entry_guide = f"Can than nguy co dam thung. Theo doi sat luc ban chu dong."
                        sl = price_nq - 18.0 if role == "SUPPORT" else price_nq + 18.0
                        tp = atm_pivot_nq
                        warning = "Thi truong Negative Gamma, bien do co the bung no manh."

            recs.append(TacticalRecommendation(
                level_name=name,
                level_price_nq=round(price_nq, 2),
                level_price_qqq=round(price_qqq, 2),
                state=state,
                action=action,
                entry_guide=entry_guide,
                stop_loss_nq=round(sl, 2),
                take_profit_nq=round(tp, 2),
                risk_warning=warning
            ))
            
        return recs
