# 📈 Neiro-NQ-Quant: Cloud-First E-mini Nasdaq Quant Terminal

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/DaniNguyen2509/-Neiro-NQ-Quant/blob/main/notebooks/Neiro_NQ_Quant.ipynb)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Zero-Waste](https://img.shields.io/badge/Zero--Waste-%3C15MB-success.svg)](README.md)

> **Hệ thống Định lượng Vi mô & Bảng điều khiển Tác chiến E-mini Nasdaq-100 (`NQ` / `MNQ` / `QQQ` / `NDX`)**  
> **Kiến trúc Cloud-First:** Vận hành 100% tự động trên **Google Colab (1-Click Run)**, lưu trữ dữ liệu nén Apache Parquet trên Google Drive, phân tích Serverless qua DuckDB, trực quan hóa Dashboard tương tác bằng Plotly.  
> ⚠️ **Thuần Python Đám mây:** Hoạt động độc lập, **KHÔNG phụ thuộc MT5 hay TradingView**.

---

## 🚀 TÁC CHIẾN NHANH TRÊN GOOGLE COLAB (1-CLICK RUN)

Chỉ cần bấm nút **[Open in Colab]** ở trên, anh có thể chạy toàn bộ hệ thống ngay trên điện thoại, iPad hoặc máy tính:
1. **Thu thập Options tự động:** Quét chuỗi quyền chọn của `QQQ` (0DTE hoặc kỳ hạn gần nhất) qua API mở.
2. **Quy đổi Basis NQ:** Tự động đồng bộ tỷ lệ giá giữa ETF QQQ và Hợp đồng tương lai E-mini Nasdaq (`NQ=F`).
3. **Giải mã ma trận Dealer (GEX & DEX):** Xác định Call Wall, Put Wall, ATM Synthetic Pivot, dải biến động kỳ vọng $\pm 1\sigma, \pm 2\sigma$, và vùng chân không thanh khoản (OI Air Pockets).
4. **Bảng điều khiển tương tác Plotly ATAS Dark Theme:** Hiển thị trực quan 3 Panels ngay trong ô kết quả của Colab hoặc lưu file HTML tương tác.
5. **Trợ lý Tác chiến AI (DeepSeek / Gemini Briefing):** Tự động xuất Kế hoạch vào lệnh, vùng mua, vùng bán, SL và cảnh báo bẫy trượt giá trước mỗi phiên (Á, Âu, Mỹ).

---

## 📚 TÀI LIỆU ĐẶC TẢ KIẾN TRÚC & DATABASE

- **Đặc tả Hệ thống (Spec):** [docs/spec.md](docs/spec.md)
- **Kiến trúc Cloud Database & Collector Pipeline:** [docs/architecture.md](docs/architecture.md)
- **Đặc tả Cấu trúc Dữ liệu Parquet & DuckDB Schema:** [docs/database-schema.md](docs/database-schema.md)

---

## 📁 CẤU TRÚC KHO LƯU TRỮ (PROJECT STRUCTURE)

```
Neiro-NQ-Quant/
├── .agents/skills/              # Agent skills
├── config/
│   └── settings.toml            # Cấu hình runtime (Ticker, GEX, Drive path)
├── docs/                        # Tài liệu đặc tả kỹ thuật và kiến trúc
│   ├── spec.md
│   ├── architecture.md
│   └── database-schema.md
├── notebooks/
│   └── Neiro_NQ_Quant.ipynb     # Google Colab Notebook All-In-One (1-Click Run)
├── src/
│   ├── collector/               # Thu thập Options QQQ/NDX & lưu trữ Parquet
│   │   ├── base.py              # Interface chuẩn BaseCollector
│   │   ├── greeks.py            # Vectorized Black-Scholes Greeks Engine
│   │   ├── nasdaq_collector.py  # Nasdaq Collector & Basis Ratio Calculator
│   │   └── storage.py           # Quản lý Parquet Partition & DuckDB
│   ├── quant_engine/            # Lõi tính toán GEX, Walls, ATM Pivot, Air Pockets
│   │   └── structure.py
│   ├── dashboard/               # Visualizer tương tác Plotly ATAS Dark Theme
│   │   └── visualizer.py
│   └── main.py                  # Entry point chạy pipeline end-to-end
├── tests/                       # Unit tests & Integration tests
│   ├── test_collector.py
│   └── test_greeks.py
├── requirements.txt
├── AGENTS.md / GEMINI.md        # Bộ quy tắc cốt lõi
└── README.md
```

---

## 🧹 QUY ĐỊNH ZERO-WASTE & LƯU TRỮ ĐÁM MÂY

- **Máy tính cá nhân (< 15MB):** Tuyệt đối không lưu trữ dữ liệu thô trên máy tính.
- **Google Drive (Cold Storage):** Toàn bộ dữ liệu options snapshot được nén Snappy Parquet siêu nhẹ (~17KB/snapshot) lưu trên Google Drive cá nhân (`/MyDrive/Neiro-NQ-Quant/data/`).
- **DuckDB Serverless (Query Engine):** Đọc trực tiếp các file Parquet trên đám mây với tốc độ < 10ms mà không tốn chi phí máy chủ.
