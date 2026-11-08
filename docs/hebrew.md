# Hebrew edition: style guide and glossary

Market Pulse has an English and a Hebrew edition. The reader switches with the language button in the
masthead (remembered per browser as `mp-lang`; a `?lang=he` or `?lang=en` link also sets it, and a
browser whose first language is Hebrew opens in Hebrew). Hebrew pages run right to left.

The Hebrew must read as if an Israeli financial journalist wrote it (the register of Globes, TheMarker or
Calcalist), not as a translation. Same facts, same numbers, same caution: it is still not financial advice.

## Where the Hebrew lives

| Text | Where |
|---|---|
| Fixed page text (headings, ledes, footers, meta) | `data-he` / `data-he-html` attributes on the element in each page |
| Text built by scripts (labels, notes, freshness lines) | `L("English", "עברית")` pairs in each page's script |
| Shared pieces (relative times, dates, sector names, insider roles, Fear & Greed ratings, buttons) | `assets/mp.js` |
| Weekly recap prose | the `he` block inside each `data/weekly/<monday>.json` (see `docs/weekly-recap.md`) |

## Voice

- Plain, short, active sentences. Write the idea in Hebrew; never mirror English word order.
- Address readers in the plural in instructions: הקישו, בחרו, נסו לרענן.
- Keep the contrarian framing: conditions, not calls. Never write קנו / מכרו / כדאי להיכנס.
- Agreement: המדד עלה, המניה עלתה, הקרן גייסה, הסקטורים ירדו, שלושה סקטורים, שלוש מניות.
- Avoid anglicisms (לוקח מקום, עושה הגיון, בסוף היום) and stacked על ידי.

## Numbers, signs and direction (bidi)

The page handles the mechanics on its own (`MP_BIDI` in `assets/mp.js`): every signed number
(−1.0%, +0.3%, ~−$1.28B) stays in one left-to-right piece, a prefix and its hyphen never end a line
apart from the number or Latin word they join (ב-2.7%, ה-S&P 500), and index names keep their number
on the same line (S&P 500, נאסד״ק 100). The writer's part:

- Digits and separators as in English: 7,376.86 · 2.7% · $98.32.
- In running text say the direction in words: עלה ב-4.9%, ירד ב-12%, ירידה של 2.7%, מינוס 100. Keep
  signs only in short value fields (flows value, stats value, consensus expected/prior, move chips).
- Ranges in running text: בין 7,620 ל-7,680. A bare 7,620–7,680 reverses visually in Hebrew text.
- A Hebrew prefix before a digit or a Latin letter takes a hyphen: ב-2026, ל-7,200, ה-S&P 500, מ-SPY, ו-10%.
- Money in prose: 120 מיליון דולר, 1.28 מיליארד דולר, 15 אלף דולר. Compact fields may keep $1K–15K, $9.6B.
- Times: 8:30 בבוקר שעון ניו יורק (ET is שעון ניו יורק). Add Israel time only when the offset is certain
  for that date (US and Israeli clocks change on different dates in March/April and October/November).
- Dates: 6 בנובמבר, ביום חמישי. Calendar day labels: שני 9, שלישי 10, רביעי 11, חמישי 12, שישי 13.
- Abbreviations use gershayim and geresh, never ASCII quotes: ארה״ב, מנכ״ל, יו״ר, נדל״ן, נאסד״ק, ג׳ונס, נ״ב.

## Keep in Latin letters

Tickers and fund symbols (NVDA, SPY, XLK, SOXX), the S&P 500, Market Pulse, Form 4 / 13F / 10b5-1,
CPI / PPI / RSI / VIX when given as the abbreviation, URLs, source titles (they name English articles),
the round monograms of the big-money rows (DT, NP: Hebrew initials too easily spell a word), and
insider names from SEC filings (the page shows them as filed).

## Glossary

### The site

| English | עברית |
|---|---|
| composite / composite score | הציון המשולב |
| signal (one of the five) | אינדיקטור |
| score / reading | ציון / ערך |
| opportunity / caution / neutral | הזדמנות / זהירות / ניטרלי |
| leaning opportunity / caution | נוטה להזדמנות / נוטה לזהירות |
| contrarian | נגד הזרם |
| stale | לא עדכני |
| context only | להקשר בלבד |
| Today / Scanner / Weekly recap | היום / סורק / סיכום שבועי |
| day edition / night edition | מהדורת יום / מהדורת לילה |
| edition (of the recap) | גיליון |
| watchlist | רשימת מעקב |
| Not financial advice. | אין באמור ייעוץ השקעות. |

### Markets

| English | עברית |
|---|---|
| stock / share / index | מניה / מניה / מדד |
| ETF | קרן סל |
| sector / sector rotation | סקטור / רוטציה בין סקטורים |
| equal-weight S&P 500 | S&P 500 שווה משקל |
| megacaps, the giants | מניות הענק, הענקיות |
| small caps | המניות הקטנות |
| bull / bear (people) | שוורים / דובים |
| bullish / bearish | שורי / דובי |
| rally / selloff / crash | ראלי / גל מכירות / קריסה |
| correction / pullback / rebound | תיקון / ירידה זמנית / התאוששות |
| record close / all-time high | נעילת שיא / שיא כל הזמנים |
| 52-week high / low | שיא 52 שבועות / שפל 52 שבועות |
| moving average; 50-, 150-, 200-day | ממוצע נע; הממוצע הנע ל-50, ל-150, ל-200 יום (קצר: ממוצע 200) |
| support / resistance | תמיכה / התנגדות |
| breakout / breakdown | פריצה / שבירה |
| trading range | טווח מסחר |
| oversold / overbought | מכירת יתר / קניית יתר |
| extended, stretched | מתוח |
| standard deviations | סטיות תקן |
| volatility / VIX | תנודתיות / מדד ה-VIX |
| volume / unusual volume | מחזור מסחר / מחזור חריג |
| market breadth / leadership | רוחב השוק / הובלה |
| close / closing price | נעילה / שער הנעילה |
| premarket / futures | טרום מסחר / החוזים העתידיים |
| earnings, results / earnings season | דוחות כספיים, תוצאות / עונת הדוחות |
| beat / missed (estimates) | עקפה את התחזיות / החטיאה את התחזיות |
| guidance / outlook | תחזית |
| revenue / gross margin / EPS | הכנסות / שיעור הרווח הגולמי / רווח למניה |
| buyback | רכישה עצמית של מניות |
| consensus | הקונצנזוס, צפי האנליסטים |
| hedge fund / leverage / deleveraging | קרן גידור / מינוף / הורדת מינוף |
| data center / chips / AI build-out | מרכז נתונים / שבבים / השקעות בתשתית בינה מלאכותית |
| capex | השקעות הוניות |

### Macro and rates

| English | עברית |
|---|---|
| the Fed / rate hike / rate cut | הפד / העלאת ריבית / הורדת ריבית |
| Fed decision / meeting | החלטת הריבית / ישיבת הפד |
| hawkish / dovish | ניצי / יוני |
| CPI / core CPI | מדד המחירים לצרכן (CPI) / מדד הליבה |
| PPI | מדד המחירים ליצרן (PPI) |
| payrolls, jobs report | דוח התעסוקה, תוספת המשרות |
| unemployment rate / wages | שיעור האבטלה / השכר |
| retail sales / GDP / PCE | המכירות הקמעונאיות / התוצר / מדד ה-PCE |
| Treasury yields / 10-year yield | תשואות האג״ח הממשלתיות / התשואה ל-10 שנים |
| basis points | נקודות בסיס (נ״ב) |
| Treasury auction | מכרז אג״ח ממשלתי |
| oil / Brent / gold / commodities | נפט / ברנט / זהב / סחורות |

### Disclosures and big money

| English | עברית |
|---|---|
| insider / insider buying | בעל עניין / קניות של בעלי עניין |
| officers, directors, 10% owners | נושאי משרה, דירקטורים ובעלי 10% מהמניות |
| open-market purchase | קנייה בשוק הפתוח |
| filing, disclosure / disclosed | דיווח / דווח |
| SEC Form 4 | טופס 4 ל-SEC |
| 10b5-1 plan | תוכנית 10b5-1 (מכירה שנקבעה מראש) |
| 13F | דוח 13F (דוח האחזקות הרבעוני) |
| periodic transaction report | דוח עסקאות תקופתי |
| short, bet against / put / call | שורט, הימור נגד / אופציית פוט / אופציית קול |
| inflows / outflows (funds) | כניסות כספים / יציאות כספים |
| spot bitcoin ETFs | קרנות הסל על ביטקוין |
| liquidity zone | אזור נזילות |
| Rep. / Sen. | חבר בית הנבחרים / הסנאטור |
| House / Senate / Congress / governor | בית הנבחרים / הסנאט / הקונגרס / מושל |
| midterms | בחירות אמצע הקדנציה |

### Sectors

| SPDR fund | עברית |
|---|---|
| XLK Technology | טכנולוגיה |
| XLF Financials | פיננסים |
| XLY Consumer Discretionary | צריכה מחזורית |
| XLC Communication Services | שירותי תקשורת |
| XLV Health Care | בריאות |
| XLI Industrials | תעשייה |
| XLP Consumer Staples | צריכה בסיסית |
| XLE Energy | אנרגיה |
| XLU Utilities | תשתיות |
| XLRE Real Estate | נדל״ן |
| XLB Materials | חומרי גלם |
| SOXX Semiconductors | שבבים |

### Names

Spell people and companies the way the Israeli financial press does. When unsure, transliterate by
pronunciation, or keep the Latin spelling; never guess a meaning.

People: דונלד טראמפ, ג׳יי. די. ואנס, ננסי פלוסי, קתי ווד, מייקל ברי, וורן באפט, גרג אייבל, ביל אקמן,
לאופולד אשנברנר, ג׳רום פאוול, לאנס רוברטס, מרקו רוביו, ג׳נסן הואנג, אילון מאסק.

Companies: אנבידיה, אפל, מיקרוסופט, אלפבית (גוגל), אמזון, מטא, טסלה, ברודקום, AMD, אינטל, מיקרון,
קוואלקום, ARM, קורוויב, סרבראס, פלנטיר, ספייס-אקס, אפלייד מטריאלס, סיסקו, אורקל, ברקשייר האת׳וויי,
בלקרוק, פידליטי, ARK, פרשינג סקוור, גולדמן זאקס, סיטדל, פאני מיי, פרדי מאק, מרקדו ליברה, קוינבייס.

Places and bodies: ארה״ב, איראן, מצר הורמוז, קטאר, הבית הלבן, משרד העבודה האמריקאי, ה-G7.

## Weekly recap: fixed page labels

| English | עברית |
|---|---|
| Week of … · published … | השבוע של … · פורסם ב… |
| Last week's calls, checked | מה אמרנו בשבוע שעבר, ומה קרה בפועל |
| Big money moves | מהלכי הכסף הגדול |
| Mind the lag. | שימו לב לפער הזמנים. |
| Names showing up twice | שמות שמופיעים יותר מפעם אחת |
| What moved markets | מה הזיז את השווקים |
| The week ahead | השבוע שלפנינו |
| The numbers to beat | הצפי בשוק |
| Odds of another Fed hike | הסיכוי להעלאת ריבית נוספת של הפד |
| Three things that decide the week | שלושה דברים שיכריעו את השבוע |
| Sources | מקורות |
