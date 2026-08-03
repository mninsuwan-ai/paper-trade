# $10,000 Paper Trade — Sector Core Portfolio

A simulated buy-and-hold portfolio that updates itself every weekday on GitHub Actions and
publishes a dashboard to GitHub Pages. **No real money, no broker, no orders. Not investment advice.**

- **Start capital:** $10,000 USD
- **Entry:** official regular-session open price of **2026-08-03**
- **Rules:** fractional shares, zero commission, no rebalancing, dividends not reinvested

| Ticker | Company | Sector | Target |
|---|---|---|---|
| MSFT | Microsoft Corp. | Technology | 15% |
| AMZN | Amazon.com Inc. | Consumer Discretionary | 15% |
| GOOGL | Alphabet Inc. | Communication Services | 15% |
| JPM | JPMorgan Chase & Co. | Financials | 10% |
| CAT | Caterpillar Inc. | Industrials | 10% |
| NEE | NextEra Energy Inc. | Utilities | 10% |
| XOM | Exxon Mobil Corp. | Energy | 10% |
| LIN | Linde plc | Materials | 5% |
| JNJ | Johnson & Johnson | Healthcare | 5% |
| PG | Procter & Gamble Co. | Consumer Staples | 5% |

---

## Setup (ทำครั้งเดียว ~5 นาที)

### 1. สร้าง repo

ไปที่ <https://github.com/new> → ตั้งชื่อเช่น `paper-trade` → เลือก **Public** → Create.
(Public เพราะ GitHub Pages ฟรีเปิดได้เฉพาะ public repo)

### 2. Push ไฟล์ในโฟลเดอร์นี้ขึ้นไป

เปิด Terminal / PowerShell ในโฟลเดอร์นี้ แล้วรัน:

```bash
git init -b main
git add .
git commit -m "init: $10k paper trade portfolio"
git remote add origin https://github.com/mninsuwan-ai/paper-trade.git
git push -u origin main
```

### 3. อนุญาตให้ Actions เขียน repo ได้

Repo → **Settings → Actions → General** → เลื่อนลงหา *Workflow permissions* →
เลือก **Read and write permissions** → Save.

### 4. เปิด GitHub Pages

Repo → **Settings → Pages** → *Source*: **Deploy from a branch** →
Branch: **main**, folder: **/ (root)** → Save.

หลังจากนั้นประมาณ 1 นาที dashboard จะอยู่ที่:

```
https://mninsuwan-ai.github.io/paper-trade/
```

### 5. รันครั้งแรกเพื่อซื้อ

Repo → แท็บ **Actions** → *Update paper-trade portfolio* → **Run workflow**.

รอบแรกจะดึงราคา **Open ของ 2026-08-03** มาเป็นราคาเข้าซื้อ คำนวณจำนวนหุ้น แล้ว commit
`portfolio.json` + `index.html` กลับเข้า repo อัตโนมัติ

---

## หลังจากนี้

Workflow รันเองทุกวันจันทร์–ศุกร์ เวลา **21:30 UTC** (≈ 04:30 น. ไทยของเช้าวันถัดไป) ซึ่งเป็นเวลาหลังตลาดสหรัฐปิดเสมอ
ทั้งฤดูร้อน (EDT) และฤดูหนาว (EST) — ไม่ต้องเปิดคอมพิวเตอร์ทิ้งไว้

> GitHub อาจดีเลย์ cron ได้ถึง ~1 ชม. ในช่วงคนใช้เยอะ ไม่มีปัญหาเพราะ job รันซ้ำได้โดยผลไม่เปลี่ยน

## ไฟล์ในโปรเจกต์

| ไฟล์ | หน้าที่ |
|---|---|
| `portfolio.json` | สถานะพอร์ต — เงินต้น, น้ำหนักเป้าหมาย, จำนวนหุ้น, ราคาเข้า, ประวัติมูลค่ารายวัน |
| `update.py` | ดึงราคาจาก Stooq (สำรอง: Yahoo Finance) แล้วอัพเดท `portfolio.json` — stdlib ล้วน ไม่ต้อง pip install |
| `build.py` | เรนเดอร์ `portfolio.json` → `index.html` |
| `index.html` | dashboard (ไฟล์ที่ Pages เสิร์ฟ — **อย่าแก้มือ** มันถูกเขียนทับทุกวัน) |
| `.github/workflows/update.yml` | ตารางรันอัตโนมัติ |

## รันเองบนเครื่อง

```bash
python3 update.py --dry-run   # ดูว่าจะได้ราคาอะไรบ้าง ไม่เขียนไฟล์
python3 update.py && python3 build.py
```

## แก้พอร์ต

แก้ `portfolio.json` แล้ว push — `target` ของทุกตัวต้องรวมได้ 1.00
ถ้าอยากเริ่มพอร์ตใหม่หมด: ตั้ง `"status": "pending_open"`, `"entry_date"` เป็นวันที่ต้องการ,
เคลียร์ `history` กับ `log` ให้เป็น `[]` แล้วตั้ง `shares`/`entry` ของทุกตัวเป็น `0`/`null`

## Troubleshooting

- **Actions รันแล้วแต่ไม่ commit** → ข้อ 3 ยังไม่ได้ตั้ง Read and write permissions
- **หน้าเว็บ 404** → ข้อ 4 ยังไม่ได้เปิด Pages หรือรอ deploy ยังไม่เสร็จ
- **บางตัวราคาไม่อัพเดท** → ผู้ให้ข้อมูลล่มชั่วคราว สคริปต์จะเก็บราคาเดิมไว้และบันทึกไว้ใน activity log แล้วลองใหม่วันถัดไป
