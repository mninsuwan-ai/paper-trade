# Paper Trade

Simulated buy-and-hold portfolios that update themselves every weekday on GitHub Actions and
publish to GitHub Pages. **No real money, no broker, no orders. Not investment advice.**

**Common rules:** fractional shares, zero commission, no rebalancing, dividends not reinvested.
Each portfolio is benchmarked against the same money put into **SPY** from its own `track_since`
date (SPY rather than `^GSPC` because Alpha Vantage's free tier does not serve index symbols).

### Sector Core &mdash; `portfolios/sector-core.json`

$10,000 spread across one large-cap leader per GICS sector, all bought at the
**2026-08-03 open**. Weights: MSFT / AMZN / GOOGL 15% each, JPM / CAT / NEE / XOM 10% each,
LIN / JNJ / PG 5% each.

### Tracking trade &mdash; `portfolios/tracking-trade.json`

The 15 largest holdings by market value from the Dime monthly statement of July 2026.
Share counts and entry prices are taken straight from the statement, so `entry` is the
reported **average cost per share** rather than a single purchase price. Cost basis
**$7,368.04** across META, AMZN, DOCN, MELI, AXON, NVDA, MSFT, CRWD, GOOGL, RBRK, AAPL,
TSLA, NBIS, TTMI, SNOW.

Because that cost basis was accumulated over many different dates, its benchmark starts on
**2026-08-05** instead, from whatever the portfolio was worth that day.

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

ถ้าไม่ใส่ก็ยังรันได้ สคริปต์จะไปลอง Stooq → Yahoo ต่อ แต่ไม่การันตี

**โควต้า** — ฟรี 25 requests/วัน ปัจจุบันใช้ **23** (หุ้นไม่ซ้ำ 22 ตัว + SPY) เหลือที่ว่าง **2 ตัว**
หุ้นที่ซ้ำกันระหว่างพอร์ตดึงครั้งเดียวแล้วใช้ร่วมกัน ดังนั้นพอร์ตใหม่ที่ประกอบจากหุ้นเดิมล้วนๆ ไม่กินโควต้าเพิ่ม

> ด้วยเหตุนี้ cron จึงตั้งไว้ **รอบเดียว** — สองรอบจะกลายเป็น 46 requests/วัน เกินโควต้า
> รอบหลังจะพังทุกตัว การกด Run workflow เองก็กินอีก 23 ครั้งเช่นกัน วันนึงกดเองได้ 1 ครั้ง

### 6. รันครั้งแรกเพื่อซื้อ

Repo → แท็บ **Actions** → *Update paper-trade portfolio* → **Run workflow**.

รอบแรกจะดึงราคา **Open ของ 2026-08-03** มาเป็นราคาเข้าซื้อ คำนวณจำนวนหุ้น แล้ว commit
`portfolios/*.json` + ไฟล์ HTML กลับเข้า repo อัตโนมัติ

> ต้องรันหลังตลาดสหรัฐปิดของวันนั้น (หลัง 04:00 น. ไทยของเช้าถัดไป) ถ้ารันก่อนหน้านั้น
> ราคา Open ยังไม่ถูกเผยแพร่ สคริปต์จะเลื่อนการซื้อออกไปและบอกใน log ว่า `buy deferred`
> ไม่ทำให้ข้อมูลเสีย รันซ้ำได้เรื่อยๆ

ขั้นแรกของ workflow ชื่อ **Probe price sources** จะทดสอบทั้ง 3 แหล่งกับ MSFT แล้วพิมพ์ผลไว้ใน log
ถ้ามีปัญหาให้ดูตรงนี้ก่อนเสมอ

---

## หลังจากนี้

Workflow รันเอง **รอบเดียว** วันอังคาร–เสาร์ (UTC) เวลา **01:07 UTC ≈ 08:07 น. ไทย**
ซึ่งครอบคลุมการปิดตลาดของจันทร์–ศุกร์ US ทั้งฤดูร้อน (EDT) และฤดูหนาว (EST)
ไม่ต้องเปิดคอมพิวเตอร์ทิ้งไว้

> GitHub **ไม่การันตี**ว่า scheduled run จะรันตรงเวลา และอาจ *ข้ามไปเลย* ถ้าตั้งไว้ตรงนาที `:00` หรือ `:30`
> ซึ่งเป็นช่วงที่คนตั้งกระจุกกัน — นั่นคือเหตุผลที่นาทีใน cron ตั้งเป็นเลขแปลกๆ
> ถ้ารอบไหนโดนข้าม กด Run workflow เองได้ (แต่กินโควต้า Alpha Vantage อีก 23 ครั้ง วันนึงจึงกดได้ครั้งเดียว)

## ไฟล์ในโปรเจกต์

| ไฟล์ | หน้าที่ |
|---|---|
| `portfolios/*.json` | สถานะของแต่ละพอร์ต — จำนวนหุ้น, ราคาเข้า, benchmark, ประวัติมูลค่ารายวัน |
| `update.py` | ดึงราคา (Alpha Vantage → Stooq → Yahoo) แล้วอัพเดททุกไฟล์ใน `portfolios/` — stdlib ล้วน |
| `build.py` | เรนเดอร์ `portfolios/*.json` → `<slug>.html` ของแต่ละพอร์ต + `index.html` หน้ารวม |
| `*.html` | dashboard (**อย่าแก้มือ** ถูกเขียนทับทุกครั้งที่รัน) |
| `.github/workflows/update.yml` | ตารางรันอัตโนมัติ |

## เพิ่มพอร์ตใหม่

สร้างไฟล์ใหม่ใน `portfolios/` แล้ว push — `build.py` กับ `update.py` จะเจอเอง ไม่ต้องแก้โค้ด

ฟิลด์สำคัญ:

| ฟิลด์ | ความหมาย |
|---|---|
| `slug` | ชื่อไฟล์ HTML ที่จะถูกสร้าง (`<slug>.html`) |
| `status` | `"pending_open"` = ให้ระบบไปหาราคา Open ของ `entry_date` มาซื้อให้ · `"open"` = ใส่ `shares`/`entry` มาเองแล้ว |
| `start_cash` | เงินต้น (ถ้า `pending_open`) หรือต้นทุนรวม (ถ้า `open`) — ใช้เป็นฐานคำนวณ Total return |
| `target` | น้ำหนักเป้าหมายของแต่ละตัว รวมต้องได้ 1.00 |
| `track_since` | วันที่เริ่มเทียบกับ S&P 500 |
| `track_base` | มูลค่าตั้งต้นของการเทียบ — ใส่ `null` ให้ระบบเก็บมูลค่าพอร์ต ณ วันแรกที่รันมาใช้เอง |

> **`track_since` / `track_base` มีไว้ทำไม:** พอร์ตที่ลอกมาจากบัญชีจริงมีต้นทุนเฉลี่ยที่เกิดจากการซื้อ
> หลายครั้งคนละเวลา เอาไปเทียบกับดัชนีตรงๆ ไม่ได้ ระบบจึงแยกเป็นสองตัวเลข —
> **Total return** (เทียบต้นทุน) กับ **Since tracking** (เทียบมูลค่าวันที่เริ่ม track ซึ่งใช้เทียบ S&P ได้)

## Projection — Monte Carlo

แต่ละหน้าพอร์ตมีการ์ด **Projection** จำลองอนาคต 4,000 เส้นทาง ปรับ horizon (1–15 ปี)
กับสมมติฐานผลตอบแทนตลาด (0–14%/ปี) ได้สดๆ ในหน้าเว็บ

**โมเดล** — one-factor: `ผลตอบแทนหุ้น = beta × ตลาด + ความผันผวนเฉพาะตัว`

- `update.py` วัด `beta`, `resid_vol`, `vol` ของแต่ละตัวจาก daily returns ย้อนหลัง ~100 วันทำการ
  โดย regress กับ SPY แล้วเก็บลง JSON
- ผลตอบแทนคาดหวังรายตัวมาจาก **CAPM** (`rf + beta × (ตลาด − rf)`, rf = 4%)
  — **ไม่ได้** เอาผลตอบแทนย้อนหลังของหุ้นตัวนั้นมาต่อเส้น
- ไม่มี rebalancing ตรงกับกติกาพอร์ต

> **ทำไมไม่ใช้ผลตอบแทนย้อนหลังของหุ้นเอง:** DOCN ขึ้นมา +334% ถ้าเอาไปต่อเส้น 8 ปี
> จะได้ตัวเลขที่ดูน่าเชื่อแต่ไร้ความหมาย การใช้ CAPM แปลว่า **ไม่สมมติว่าเลือกหุ้นเก่ง**
> ความกว้างของกราฟที่เห็นคือความผันผวน ไม่ใช่คำทำนายเกี่ยวกับบริษัทเหล่านี้

**ข้อจำกัดที่ต้องรู้** — lognormal จับได้แค่ความผันผวน ไม่ได้จับการถูกซื้อกิจการ, dilution,
เปลี่ยน regime, หรือบริษัทเจ๊ง และ beta วัดจาก ~100 วันซึ่งสั้น ค่าจะขยับได้พอสมควรตามช่วงเวลา
ใช้ดูขนาดคร่าวๆ เท่านั้น ไม่ใช่คำแนะนำการลงทุน

### เรื่อง stock split

endpoint ฟรีของ Alpha Vantage (`TIME_SERIES_DAILY`) ให้ราคา **as-traded ไม่ปรับ split**
(ตัวที่ปรับแล้วเป็นของเสียเงิน) ถ้ามีการแตกพาร์ในช่วงที่ใช้คำนวณ จะเห็นเป็นวันที่ราคาร่วง 50%
ทั้งที่ไม่มีอะไรเกิดขึ้นจริง

`update.py` จึงตัด daily return ที่เกิน ±35% ออกจากการคำนวณสถิติ (ค่าคงที่ `SPLIT_GUARD`)
แล้วบันทึกไว้ที่ `stat_dropped` ของหุ้นตัวนั้น พร้อมขึ้นหมายเหตุบนการ์ด Projection ว่าตัดของตัวไหนไปกี่วัน

> วัดผลจากข้อมูลทดสอบที่ฝัง split 2:1 ไว้: ถ้าไม่ตัด residual vol จะกลายเป็น **1.075**
> ถ้าตัดจะได้ **0.290** เทียบค่าจริง 0.300 — วันเดียวทำพังได้ทั้งตัว
> (ของจริงบนเว็บก่อนแก้ CRWD ขึ้น 2.28 คือ 228%/ปี)
>
> ผลข้างเคียงที่ยอมรับ: ถ้าหุ้นเคลื่อนไหวเกิน 35% ในวันเดียวจริงๆ (earnings shock, takeover)
> ระบบจะตัดทิ้งด้วย ทำให้ประเมินความเสี่ยง **ต่ำกว่าความจริงเล็กน้อย** ซึ่งเป็นทางเลือกที่ตั้งใจ
> เพราะการปล่อยให้ split ปนเข้ามาเสียหายกว่ามาก

## Stress test — market drawdown

การ์ด **Stress test** ตอบว่า "ถ้าตลาดลง X% พอร์ตนี้จะเหลือเท่าไร" โดยใช้ beta ของแต่ละตัว
ปรับความลึก (5–60%) และระยะเวลา (1–30 เดือน) ได้ พร้อมปุ่ม preset จากเหตุการณ์จริง
(peak-to-trough ของ S&P 500 ปัดเศษ)

| Preset | ตลาดลง | ระยะเวลา |
|---|---|---|
| COVID 2020 | 34% | 1 เดือน |
| 2022 bear | 25% | 9 เดือน |
| GFC 2007–09 | 57% | 17 เดือน |
| Dot-com 2000–02 | 49% | 31 เดือน |

**สูตร** — หุ้นแต่ละตัวเคลื่อนที่ `exp(beta × ln(1 + ผลตอบแทนตลาด))` บวกความผันผวนเฉพาะตัว
ที่ scale ตามระยะเวลาช็อก ใช้ log จึงไม่มีทางติดลบเกิน 100% (beta 2.0 กับตลาด −30%
ได้ −51% ไม่ใช่ −60%)

> **อ่านผลอย่างระวัง** — ตัวเลขนี้เป็น**ขอบล่างแบบมองโลกในแง่ดี** ไม่ใช่กรณีเลวร้ายสุด
> เพราะในวิกฤตจริง correlation ระหว่างหุ้นวิ่งเข้าหา 1 การกระจายความเสี่ยงช่วยได้น้อยกว่าที่โมเดลคิด
> และ beta ที่วัดจากวันปกติมักสูงขึ้นในภาวะตื่นตระหนก

## รันเองบนเครื่อง

```bash
python3 update.py --probe     # ทดสอบว่าแหล่งราคาไหนใช้ได้บ้าง
python3 update.py --dry-run   # ดูว่าจะได้ราคาอะไรบ้าง ไม่เขียนไฟล์
python3 update.py && python3 build.py
```

## แก้พอร์ตเดิม

แก้ไฟล์ใน `portfolios/` แล้ว push — `target` ของทุกตัวต้องรวมได้ 1.00
ถ้าอยากรีเซ็ตพอร์ตใดพอร์ตหนึ่ง: ตั้ง `"status": "pending_open"`, `"entry_date"` เป็นวันที่ต้องการ,
เคลียร์ `history` / `log` ให้เป็น `[]`, ตั้ง `shares`/`entry` ทุกตัวเป็น `0`/`null`
และตั้ง `track_base` เป็น `null` กับ `benchmark.entry` เป็น `null` ด้วย

## Troubleshooting

- **เว็บค้างที่ข้อมูลเก่า ทั้งที่ไฟล์บน main ใหม่แล้ว** → job `deploy` ไม่ได้รัน
  เทียบกันได้ที่ `raw.githubusercontent.com/.../main/portfolios/sector-core.json` (ของจริงใน repo) กับ
  `mninsuwan-ai.github.io/paper-trade/portfolios/sector-core.json` (ของที่เผยแพร่) ถ้า `last_updated` ไม่ตรงกันคือ deploy ไม่ทำงาน
- **`deploy-pages` ฟ้อง `Get Pages site failed` / 404** → Settings → Pages ยังไม่ได้ตั้ง Source เป็น GitHub Actions
- **หน้าเว็บ 404 ตอนตั้งครั้งแรก** → deploy รอบแรกใช้เวลาสักพัก รอ 2-3 นาทีแล้ว hard refresh (Ctrl+F5)
- **`Price fetch failed for: MSFT, AMZN, ...` ทุกตัว** → Stooq/Yahoo บล็อก IP ของ runner ทำตามข้อ 5
  ใส่ `ALPHAVANTAGE_KEY` ดูขั้น *Probe price sources* ใน Actions log จะบอกว่าแต่ละแหล่งตอบอะไรกลับมา
- **`buy deferred` / `open not published yet`** → รันเร็วไป ตลาดของวัน `entry_date` ยังไม่ปิด รอแล้ว Run workflow ใหม่
- **Actions รันแล้วแต่ไม่ commit** → ข้อ 3 ยังไม่ได้ตั้ง Read and write permissions
- **ถึงเวลาแล้วแต่ไม่รันเอง** → ปกติของ GitHub cron ที่ไม่การันตีเวลา กด Run workflow เองได้เลย
  ถ้าโดนข้ามบ่อยให้ขยับนาทีใน cron หนีจาก `:00` / `:30` (ดูหัวข้อ *หลังจากนี้*)
- **บางตัวราคาไม่อัพเดท** → ผู้ให้ข้อมูลล่มชั่วคราว สคริปต์จะเก็บราคาเดิมไว้และบันทึกไว้ใน activity log แล้วลองใหม่วันถัดไป
