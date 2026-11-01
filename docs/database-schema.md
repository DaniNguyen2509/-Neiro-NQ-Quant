# Đặc tả Cấu trúc Dữ liệu & Schema Database (Database Schema Spec)

> **Dự án:** Neiro-NQ-Quant  
> **Định dạng chuẩn:** Apache Parquet (Storage) & DuckDB (Query) & JSON (Dashboard Feed & Bot Signals)

---

## 1. SCHEMA SNAPSHOT OPTIONS CHAIN (PARQUET)

Mỗi lần Collector quét thị trường, một snapshot đầy đủ được lưu lại dưới dạng file `.parquet` với cấu trúc cột như sau:

| Tên Cột | Kiểu Dữ Liệu (PyArrow) | Đơn vị | Ý nghĩa / Mô tả |
|---|---|---|---|
| `snapshot_time` | `timestamp[us, tz=UTC]` | UTC Time | Thời điểm ghi nhận dữ liệu |
| `symbol` | `string` | Ticker | Ký hiệu tài sản cơ sở (VD: `QQQ`, `NDX`) |
| `underlying_price` | `float64` | USD | Giá Spot/Thị trường hiện tại của tài sản cơ sở |
| `nq_futures_price` | `float64` | USD | Giá Hợp đồng tương lai E-mini Nasdaq (`NQ=F`) |
| `basis_ratio` | `float64` | Ratio | Tỷ lệ quy đổi: $NQ\_Price / Underlying\_Price$ |
| `expiration_date` | `string` | YYYY-MM-DD | Ngày đáo hạn của Options |
| `dte` | `float64` | Days | Số ngày còn lại đến đáo hạn (tính dynamic theo giờ New York) |
| `strike` | `float64` | USD | Giá thực hiện quyền chọn |
| `strike_nq_equivalent` | `float64` | USD | Mức giá E-mini Nasdaq tương đương $(Strike \times Basis)$ |
| `call_bid` | `float64` | USD | Giá chào mua Call tốt nhất của Market Maker |
| `call_ask` | `float64` | USD | Giá chào bán Call tốt nhất |
| `call_mid` | `float64` | USD | Giá trung bình $(Bid + Ask) / 2$ |
| `call_volume` | `int64` | Contracts | Khối lượng giao dịch Call trong phiên |
| `call_oi` | `int64` | Contracts | Vị thế mở (Open Interest) của Call |
| `call_iv` | `float64` | Decimal | Biến động ngầm định (Implied Volatility) của Call |
| `call_delta` | `float64` | Decimal | Độ nhạy Delta của Call $[0, 1]$ (Black-76) |
| `call_gamma` | `float64` | Decimal | Gia tốc Gamma của Call (Black-76) |
| `call_vega` | `float64` | Decimal | Độ nhạy Vega của Call |
| `call_vanna` | `float64` | Decimal | Độ nhạy Vanna của Call |
| `call_charm` | `float64` | Decimal | Độ nhạy Charm của Call |
| `put_bid` | `float64` | USD | Giá chào mua Put tốt nhất |
| `put_ask` | `float64` | USD | Giá chào bán Put tốt nhất |
| `put_mid` | `float64` | USD | Giá trung bình Put |
| `put_volume` | `int64` | Contracts | Khối lượng giao dịch Put |
| `put_oi` | `int64` | Contracts | Vị thế mở (Open Interest) của Put |
| `put_iv` | `float64` | Decimal | Biến động ngầm định của Put |
| `put_delta` | `float64` | Decimal | Độ nhạy Delta của Put $[-1, 0]$ (Black-76) |
| `put_gamma` | `float64` | Decimal | Gia tốc Gamma của Put (Black-76) |
| `put_vega` | `float64` | Decimal | Độ nhạy Vega của Put |
| `put_vanna` | `float64` | Decimal | Độ nhạy Vanna của Put |
| `put_charm` | `float64` | Decimal | Độ nhạy Charm của Put |
| `call_gex` | `float64` | $ Millions | Giá trị Gamma Exposure của Call |
| `put_gex` | `float64` | $ Millions | Giá trị Gamma Exposure của Put (âm) |
| `net_gex` | `float64` | $ Millions | $Call\_GEX + Put\_GEX$ |
| `net_vex` | `float64` | $ Millions | Dòng Vanna phòng hộ ròng ($M/1% IV) |
| `net_chex` | `float64` | $ Millions | Dòng Charm phân rã phòng hộ ròng ($M/ngày) |

---

## 2. TRUY VẤN DUCKDB SERVERLESS (SQL ANALYTICAL EXAMPLES)

DuckDB có thể đọc trực tiếp các file Parquet mà không cần nạp toàn bộ vào RAM:

```sql
-- 1. Tìm Call Wall và Put Wall của phiên gần nhất:
SELECT 
    symbol,
    expiration_date,
    MAX(CASE WHEN call_oi = max_call_oi THEN strike_nq_equivalent END) AS call_wall_nq,
    MAX(CASE WHEN put_oi = max_put_oi THEN strike_nq_equivalent END) AS put_wall_nq
FROM (
    SELECT *,
           MAX(call_oi) OVER() as max_call_oi,
           MAX(put_oi) OVER() as max_put_oi
    FROM read_parquet('data/options/**/*.parquet')
    WHERE snapshot_time = (SELECT MAX(snapshot_time) FROM read_parquet('data/options/**/*.parquet'))
)
GROUP BY symbol, expiration_date;

-- 2. Tìm điểm Gamma Flip (Điểm mà Net GEX đảo dấu từ Dương sang Âm):
SELECT strike_nq_equivalent, net_gex
FROM read_parquet('data/options/**/*.parquet')
WHERE snapshot_time = (SELECT MAX(snapshot_time) FROM read_parquet('data/options/**/*.parquet'))
ORDER BY strike ASC;
```

---

## 3. SCHEMA DỮ LIỆU TÁC CHIẾN (TACTICAL FEED JSON: `exports/nq_tactical_levels.json`)

File `exports/nq_tactical_levels.json` được sinh tự động sau mỗi lần chạy pipeline để cung cấp tín hiệu cho Trading Bot, Telegram Webhook, Discord Bot hoặc MetaTrader 5 Expert Advisor (EA):

```json
{
  "timestamp": "2026-11-01T06:52:20.891388+00:00",
  "symbol": "NQ",
  "futures_symbol": "NQ=F",
  "source": "yfinance",
  "metrics": {
    "spot_price": 28568.77,
    "s_implied": 28568.77,
    "spot_mt5": 28568.77,
    "basis_offset": 0.0,
    "multiplier": 20.0,
    "effective_multiplier": 20.0,
    "atm_strike": 28514.0,
    "atm_straddle": 426.26,
    "sigma_atm": 0.2803,
    "expected_move_1s": 534.23,
    "intraday_rule16_move": 500.41,
    "upper_band_1s": 29103.0,
    "lower_band_1s": 28034.54,
    "upper_band_2s": 29637.22,
    "lower_band_2s": 27500.31,
    "call_wall": 29960.0,
    "call_wall_oi": 9649,
    "put_wall": 28720.0,
    "put_wall_oi": 8691,
    "pin_risk_magnet": 29960.0,
    "total_net_gex": -4044.95,
    "total_net_vex": -30.92,
    "total_net_chex": 13.6,
    "regime": "NEGATIVE_GAMMA_VOLATILE_EXPANSION",
    "regime_description": "Dealer khuếch đại xu hướng (Mua đuổi khi tăng, Bán tháo khi giảm). Cực kỳ nguy hiểm khi thủng cản.",
    "step": 41.0,
    "buffer_val": 6.15,
    "squeeze_trigger": 29962.07,
    "waterfall_trigger": 28432.59,
    "strike_above": 28720.0,
    "next_above": 28927.0,
    "strike_below": 28514.0,
    "next_below": 28307.0,
    "secondary_support": 28307.0,
    "raw_source": "yfinance",
    "dte_days": 0.35,
    "risk_free_rate": 0.0397,
    "real_candles": {
      "1m": [
        {
          "time": 1793386320,
          "open": 28253.25,
          "high": 28260.75,
          "low": 28232.75,
          "close": 28235.0,
          "volume": 2773
        }
      ]
    }
  },
  "tactical_recommendations": [
    {
      "level_name": "CALL WALL #1",
      "level_price_nq": 29960.0,
      "state": "DORMANT",
      "action": "MONITORING",
      "entry_guide": "Dung ngoai quan sat. Gia cach level 1391.2 diem NQ.",
      "stop_loss_nq": 29980.0,
      "take_profit_nq": 28514.0,
      "risk_warning": "Chua co phan ung vi mo."
    },
    {
      "level_name": "PUT WALL #1",
      "level_price_nq": 28720.0,
      "state": "DORMANT",
      "action": "MONITORING",
      "entry_guide": "Dung ngoai quan sat. Gia cach level 151.2 diem NQ.",
      "stop_loss_nq": 28700.0,
      "take_profit_nq": 28514.0,
      "risk_warning": "Chua co phan ung vi mo."
    },
    {
      "level_name": "ATM SYNTHETIC PIVOT",
      "level_price_nq": 28568.77,
      "state": "TRIGGERED",
      "action": "LONG_REVERSAL",
      "entry_guide": "Limit Long o 28568.77 khi M1/M5 xuat hien nen rut chan.",
      "stop_loss_nq": 28548.77,
      "take_profit_nq": 28720.0,
      "risk_warning": "Muc can luong cuc. Quan sat sat phan ung delta."
    }
  ]
}
```
