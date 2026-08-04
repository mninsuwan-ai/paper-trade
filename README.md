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

Repo → **Settings → Pages** → *Source*: เลือก **GitHub Actions** (ไม่ใช่ "Deploy from a branch")

> สำคัญ: job `deploy` ใน workflow คือตัวที่เผยแพร่หน้าเว็บจริงๆ การ commit `index.html` เข้า main
> เป็นแค่การเก็บไฟล์ไว้ใน repo — **ไม่ได้ทำให้หน้าเว็บอัพเดท** ถ้าลบ job `deploy` ออก
> หน้าเว็บจะค้างอยู่ที่ deployment ล่าสุดตลอดไป

dashboard จะอยู่ที่:

```
https://mninsuwan-ai.github.io/paper-trade/
```

### 5. ใส่ Alpha Vantage key (แนะนำอย่างยิ่ง)

Stooq กับ Yahoo มักบล็อก IP ของ GitHub runner (ตอบ 403 / 429) ทำให้ดึงราคาไม่ได้เลย
ทางแก้ที่ชัวร์คือใส่ API key ฟรีของ Alpha Vantage:

1. ขอ key ที่ <https://www.alphavantage.co/support/#api-key> (กรอกอีเมล ได้ทันที ไม่ต้องผูกบัตร)
2. Repo → **Settings → Secrets and variables → Actions → New repository secret**
3. Name: `ALPHAVANTAGE_KEY` — Secret: key ที่ได้มา → Add secret

โควต้าฟรี 25 requests/วัน พอร์ตนี้ใช้วันละ 10 — เหลือเฟือ
ถ้าไม่ใส่ก็ยังรันได้ สคริปต์จะไปลอง Stooq → Yahoo ต่อ แต่ไม่การันตี

### 6. รันครั้งแรกเพื่อซื้อ

Repo → แท็บ **Actions** → *Update paper-trade portfolio* → **Run workflow**.

รอบแรกจะดึงราคา **Open ของ 2026-08-03** มาเป็นราคาเข้าซื้อ คำนวณจำนวนหุ้น แล้ว commit
`portfolio.json` + `index.html` กลับเข้า repo อัตโนมัติ

> ต้องรันหลังตลาดสหรัฐปิดของวันนั้น (หลัง 04:00 น. ไทยของเช้าถัดไป) ถ้ารันก่อนหน้านั้น
> ราคา Open ยังไม่ถูกเผยแพร่ สคริปต์จะเลื่อนการซื้อออกไปและบอกใน log ว่า `buy deferred`
> ไม่ทำให้ข้อมูลเสีย รันซ้ำได้เรื่อยๆ

ขั้นแรกของ workflow ชื่อ **Probe price sources** จะทดสอบทั้ง 3 แหล่งกับ MSFT แล้วพิมพ์ผลไว้ใน log
ถ้ามีปัญหาให้ดูตรงนี้ก่อนเสมอ

---

## หลังจากนี้

Workflow รันเองวันอังคาร–เสาร์ (UTC) เวลา **01:07 UTC ≈ 08:07 น. ไทย** ซึ่งครอบคลุมการปิดตลาดของจันทร์–ศุกร์ US
ทั้งฤดูร้อน (EDT) และฤดูหนาว (EST) — ไม่ต้องเปิดคอมพิวเตอร์ทิ้งไว้

มีรอบสำรองอีกรอบที่ **05:23 UTC ≈ 12:23 น. ไทย**

> GitHub **ไม่การันตี**ว่า scheduled run จะรันตรงเวลา และอาจ *ข้ามไปเลย* ถ้าตั้งไว้ตรงนาที `:00` หรือ `:30`
> ซึ่งเป็นช่วงที่คนตั้งกระจุกกัน — นั่นคือเหตุผลที่ cron ในไฟล์นี้ตั้งนาทีแปลกๆ และมี 2 รอบ
> job รันซ้ำได้โดยผลไม่เปลี่ยน จึงไม่มีผลเสียถ้ารันทั้งสองรอบ

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
python3 update.py --probe     # ทดสอบว่าแหล่งราคาไหนใช้ได้บ้าง
python3 update.py --dry-run   # ดูว่าจะได้ราคาอะไรบ้าง ไม่เขียนไฟล์
python3 update.py && python3 build.py
```

## แก้พอร์ต

แก้ `portfolio.json` แล้ว push — `target` ของทุกตัวต้องรวมได้ 1.00
ถ้าอยากเริ่มพอร์ตใหม่หมด: ตั้ง `"status": "pending_open"`, `"entry_date"` เป็นวันที่ต้องการ,
เคลียร์ `history` กับ `log` ให้เป็น `[]` แล้วตั้ง `shares`/`entry` ของทุกตัวเป็น `0`/`null`

## Troubleshooting

- **เว็บค้างที่ข้อมูลเก่า ทั้งที่ `portfolio.json` บน main ใหม่แล้ว** → job `deploy` ไม่ได้รัน
  เทียบกันได้ที่ `raw.githubusercontent.com/.../main/portfolio.json` (ของจริงใน repo) กับ
  `mninsuwan-ai.github.io/paper-trade/portfolio.json` (ของที่เผยแพร่) ถ้า `last_updated` ไม่ตรงกันคือ deploy ไม่ทำงาน
- **`deploy-pages` ฟ้อง `Get Pages site failed` / 404** → Settings → Pages ยังไม่ได้ตั้ง Source เป็น GitHub Actions
- **หน้าเว็บ 404 ตอนตั้งครั้งแรก** → deploy รอบแรกใช้เวลาสักพัก รอ 2-3 นาทีแล้ว hard refresh (Ctrl+F5)
- **`Price fetch failed for: MSFT, AMZN, ...` ทุกตัว** → Stooq/Yahoo บล็อก IP ของ runner ทำตามข้อ 5
  ใส่ `ALPHAVANTAGE_KEY` ดูขั้น *Probe price sources* ใน Actions log จะบอกว่าแต่ละแหล่งตอบอะไรกลับมา
- **`buy deferred` / `open not published yet`** → รันเร็วไป ตลาดของวัน `entry_date` ยังไม่ปิด รอแล้ว Run workflow ใหม่
- **Actions รันแล้วแต่ไม่ commit** → ข้อ 3 ยังไม่ได้ตั้ง Read and write permissions
- **ถึงเวลาแล้วแต่ไม่รันเอง** → ปกติของ GitHub cron ที่ไม่การันตีเวลา กด Run workflow เองได้เลย
  ถ้าโดนข้ามบ่อยให้ขยับนาทีใน cron หนีจาก `:00` / `:30` (ดูหัวข้อ *หลังจากนี้*)
- **บางตัวราคาไม่อัพเดท** → ผู้ให้ข้อมูลล่มชั่วคราว สคริปต์จะเก็บราคาเดิมไว้และบันทึกไว้ใน activity log แล้วลองใหม่วันถัดไป
