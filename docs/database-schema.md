# Đặc tả Cấu trúc Dữ liệu & Schema Database (Database Schema Spec)

> **Dự án:** Neiro-NQ-Quant  
> **Định dạng chuẩn:** Apache Parquet (Storage) & DuckDB (Query) & JSON (Dashboard Feed)

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
| `dte` | `float64` | Days | Số ngày còn lại đến đáo hạn |
| `strike` | `float64` | USD | Giá thực hiện quyền chọn |
| `strike_nq_equivalent` | `float64` | USD | Mức giá E-mini Nasdaq tương đương $(Strike \times Basis)$ |
| `call_bid` | `float64` | USD | Giá chào mua Call tốt nhất của Market Maker |
| `call_ask` | `float64` | USD | Giá chào bán Call tốt nhất |
| `call_mid` | `float64` | USD | Giá trung bình $(Bid + Ask) / 2$ |
| `call_volume` | `int64` | Contracts | Khối lượng giao dịch Call trong phiên |
| `call_oi` | `int64` | Contracts | Vị thế mở (Open Interest) của Call |
| `call_iv` | `float64` | Decimal | Biến động ngầm định (Implied Volatility) của Call |
| `call_delta` | `float64` | Decimal | Độ nhạy Delta của Call $[0, 1]$ |
| `call_gamma` | `float64` | Decimal | Gia tốc Gamma của Call |
| `put_bid` | `float64` | USD | Giá chào mua Put tốt nhất |
| `put_ask` | `float64` | USD | Giá chào bán Put tốt nhất |
| `put_mid` | `float64` | USD | Giá trung bình Put |
| `put_volume` | `int64` | Contracts | Khối lượng giao dịch Put |
| `put_oi` | `int64` | Contracts | Vị thế mở (Open Interest) của Put |
| `put_iv` | `float64` | Decimal | Biến động ngầm định của Put |
| `put_delta` | `float64` | Decimal | Độ nhạy Delta của Put $[-1, 0]$ |
| `put_gamma` | `float64` | Decimal | Gia tốc Gamma của Put |
| `call_gex` | `float64` | $ Millions | Giá trị Gamma Exposure của Call |
| `put_gex` | `float64` | $ Millions | Giá trị Gamma Exposure của Put (âm) |
| `net_gex` | `float64` | $ Millions | $Call\_GEX + Put\_GEX$ |
| `net_dex` | `float64` | $ Millions | Dòng Delta phòng hộ ròng của Dealer |

---

## 2. TRUY VẤN DUCKDB SERVERLESS (SQL ANALYTICAL EXAMPLES)

DuckDB có thể đọc trực tiếp nhiều file Parquet trên Google Drive mà không cần nạp vào RAM máy chủ:

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
    FROM read_parquet('/content/drive/MyDrive/Neiro-NQ-Quant/data/options/**/*.parquet')
    WHERE snapshot_time = (SELECT MAX(snapshot_time) FROM read_parquet('/content/drive/MyDrive/Neiro-NQ-Quant/data/options/**/*.parquet'))
)
GROUP BY symbol, expiration_date;

-- 2. Tìm điểm Gamma Flip (Điểm mà Net GEX đảo dấu từ Dương sang Âm):
SELECT strike_nq_equivalent, net_gex
FROM read_parquet('/content/drive/MyDrive/Neiro-NQ-Quant/data/options/**/*.parquet')
WHERE snapshot_time = (SELECT MAX(snapshot_time) FROM read_parquet('/content/drive/MyDrive/Neiro-NQ-Quant/data/options/**/*.parquet'))
ORDER BY strike ASC;
```

---

## 3. SCHEMA DỮ LIỆU TÁC CHIẾN (TACTICAL DASHBOARD JSON)

Dữ liệu tổng hợp được tính toán để đưa lên Bảng điều khiển Plotly và Prompt AI:

```json
{
  "timestamp": "2026-10-18T22:30:00Z",
  "underlying": {
    "symbol": "QQQ",
    "spot_price": 502.45,
    "nq_futures_price": 20600.45,
    "basis_ratio": 41.00
  },
  "regime": {
    "total_net_gex": 142.5,
    "state": "POSITIVE_GAMMA_MEAN_REVERTING",
    "description": "Dealer mua khi gia giam, ban khi gia tang. Bien do bi nen chat."
  },
  "key_levels_nq": {
    "call_wall": 20800.0,
    "put_wall": 20400.0,
    "absolute_gamma_strike": 20600.0,
    "atm_synthetic_pivot": 20585.0,
    "upper_expected_move_1s": 20730.0,
    "lower_expected_move_1s": 20440.0,
    "air_pockets": [
      {"from": 20380.0, "to": 20250.0, "risk": "HIGH_VACUUM_CASCADE"}
    ]
  }
}
```
