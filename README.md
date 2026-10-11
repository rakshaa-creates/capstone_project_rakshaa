# Mamaearth Returns and Growth Analysis

This project looks at Mamaearth order data to find out where returns are hurting the business. It has three parts that work one after the other:

1. **SQL** stores the data in a database and answers basic business questions.
2. **Python (pandas)** cleans the data, finds the real patterns and saves the final numbers.
3. **GenAI narrator** takes those numbers and writes a short report (Situation, Complication, Resolution) for ops and finance teams.

## Repo structure

```
README.md
requirements.txt
sql/
    schema.sql           creates the 3 tables
    seed_data.sql        inserts the data from the CSV files (safe to run again, it clears the tables first)
    reports.sql          9 report queries with their output in comments
data/
    customers.csv        45 customers
    products.csv         16 products
    orders.csv           180 orders (raw, never edited by hand)
analysis/
    clean_and_eda.py     cleaning, analysis, writes narrator/findings.json
    visualize.py         makes the 2 charts
visualizations/
    return_rate_by_payment.png
    monthly_revenue_trend.png
narrator/
    findings.json        final numbers from the analysis (created by clean_and_eda.py)
    generate_narrative.py  writes the SCR report (Gemini or offline)
    sample_output.txt    saved narrative, re-checked by the accuracy checker
```

## What you need

Python 3 and these packages:

```
pip install -r requirements.txt
```

`google-genai` is only needed for the Gemini part. The offline mode works without it. SQLite is needed for Step 1 (the `sqlite3` command line, or any SQLite tool).

## How to run (in this order)

### Step 1: SQL

Run these from the main repo folder:

```
sqlite3 mamaearth.db < sql/schema.sql
sqlite3 mamaearth.db < sql/seed_data.sql
sqlite3 mamaearth.db < sql/reports.sql
```

After loading, the tables have 45 customers, 16 products and 180 orders. `reports.sql` prints the results of reports a to i. The expected output of each one is written as a comment above the query. If you want to run `reports.sql` again, start again from `schema.sql` because report (i) adds a column and `schema.sql` drops and recreates the tables. `seed_data.sql` can be run any number of times because it empties the tables first.

### Step 2: Python analysis

```
python analysis/clean_and_eda.py
python analysis/visualize.py
```

`clean_and_eda.py` reads the CSV files directly (it does not use the SQL database). It prints every result: cleaning, outliers, return rates, correlation and monthly revenue. At the end it **writes `narrator/findings.json`**. `visualize.py` saves the two charts into `visualizations/`.

### Step 3: Narrator

With no API key (offline mode, no internet needed):

```
python narrator/generate_narrative.py
```

With a Gemini API key (free key from Google AI Studio):

Windows (PowerShell):
```
$env:GEMINI_API_KEY="your_key_here"
python narrator/generate_narrative.py
```

Mac or Linux:
```
export GEMINI_API_KEY="your_key_here"
python narrator/generate_narrative.py
```

The script tries a short list of current Gemini models in order (Google retires old ones, and a 404 means a model is not available to your key). You can force one with GEMINI_MODEL. If the key is missing or every Gemini call fails, it uses the offline version. The script then checks that the 5 important figures are in the text and prints PASS or FAIL for each. When Gemini works, the output is saved to `narrator/sample_output.txt` and checked as well.

## How the three parts connect

```
data/*.csv
   |
   |--> sql/ (schema + seed + reports)     raw totals, for example revenue 99,860.20
   |
   |--> analysis/clean_and_eda.py          cleans data, revenue becomes 97,358.30
              |
              |--> narrator/findings.json  the verified numbers
                        |
                        |--> narrator/generate_narrative.py  -> SCR report
```

- The SQL raw revenue (99,860.20) is compared with the cleaned pandas revenue (97,358.30). The gap of 2,501.90 is exactly the value of the 5 duplicate orders.
- The narrator only uses numbers from `findings.json`, it never makes up its own.

## Main results

- Cleaned revenue: Rs 97,358.30 (175 orders after removing 5 duplicates)
- Return rate: COD 44.4%, UPI 18.9%, Card 14.7%
- Highest risk segment: COD orders in Tier-2 cities, 54.5% returns
- January only looked like the best month because of two bulk orders (25 and 30 units). After removing them, March is the real peak month with Rs 20,318.90
- Discount and returns are not related (correlation about -0.09)

## Why I made these choices

- **Duplicates:** the 5 duplicate orders (O0176 to O0180) match an earlier order on every column except `order_id`, so I treated them as double-submits and removed them before filling blanks.
- **Missing values:** a blank discount means no discount, so it becomes 0. A blank rating becomes the median because the median is not pulled by extreme values.
- **Outliers:** the IQR rule flags quantities far from the middle. I flag them and keep the rows. They are removed only when drawing the monthly trend, so the two bulk orders do not make January look like the best month.
- **Numbers:** `findings.json`, the charts and the narrator prompt are all built from computed values, nothing is typed in by hand.
- **Narrator:** temperature 0 so the report is repeatable, a 30 second timeout (in milliseconds), and an offline template so the project always runs with no key. The accuracy checker confirms that 5 key figures appear in the text.

## Note on sample_output.txt

`sample_output.txt` holds the last narrative that was saved. It is overwritten with the real Gemini text each time `generate_narrative.py` runs successfully with a `GEMINI_API_KEY`. If you never ran it with a key, it contains the offline narrative.
