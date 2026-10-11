# Mamaearth Returns and Growth Analysis

## About this project

Hi, I'm Rakshaa Shrivastav, and I built this project as part of my data analytics capstone. I chose to focus on Mamaearth's order returns because I wanted to understand how data can help identify problems that affect a business's revenue. What surprised me most was that COD orders in Tier-2 cities had a 54.5% return rate, and January's high revenue was largely influenced by just two bulk orders. If I were to take this project further, I would look into the reasons behind these returns and explore ways to help the business reduce them.

This project uses Mamaearth order data to understand where returns are affecting the business. It has three parts that work together:

1. **SQL** stores the data in a database and answers basic business questions.
2. **Python (pandas)** cleans the data, finds patterns and saves the final numbers.
3. **GenAI narrator** uses those numbers to write a short report in Situation, Complication, Resolution format for operations and finance teams.

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

You need Python 3 and the following packages:

```
pip install -r requirements.txt
```

`google-genai` is only needed for the Gemini part. The offline mode works without it. SQLite is needed for Step 1 (`sqlite3` command line, or any SQLite tool).

## How to run (in this order)

### Step 1: SQL

Run these commands from the main repo folder:

```
sqlite3 mamaearth.db < sql/schema.sql
sqlite3 mamaearth.db < sql/seed_data.sql
sqlite3 mamaearth.db < sql/reports.sql
```

If you do not have the `sqlite3` command, you can run the same files with Python instead:

```
python -c "import sqlite3; c = sqlite3.connect('mamaearth.db'); [c.executescript(open(f).read()) for f in ('sql/schema.sql', 'sql/seed_data.sql', 'sql/reports.sql')]; print('SQL files ran successfully')"
```

After loading the data, the tables contain 45 customers, 16 products and 180 orders. `reports.sql` displays the results of reports a to i. The expected output for each report is included in a comment above its query.

If you want to run `reports.sql` again, start from `schema.sql` because report (i) adds a column and `schema.sql` drops and recreates the tables. You can run `seed_data.sql` any number of times because it clears the tables before inserting the data again.

### Step 2: Python analysis

Run the following commands:

```
python analysis/clean_and_eda.py
python analysis/visualize.py
```

`clean_and_eda.py` reads the CSV files directly instead of using the SQL database. It prints the results of the cleaning process, outlier checks, return rates, correlation and monthly revenue analysis. At the end, it **writes `narrator/findings.json`** with the final numbers.

`visualize.py` creates the two charts and saves them in `visualizations/`.

### Step 3: Narrator

You can run the narrator without an API key using offline mode. It does not need an internet connection:

```
python narrator/generate_narrative.py
```

To use Gemini, first get a free API key from Google AI Studio.

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

The script tries a short list of current Gemini models in order because Google sometimes retires older models. A 404 means a model is not available to your key. You can choose a specific model using `GEMINI_MODEL`.

If the API key is missing or all Gemini calls fail, the script switches to the offline version. After generating the report, it checks whether the 5 important figures appear in the text and prints PASS or FAIL for each check. When Gemini works, the generated report is also saved to `narrator/sample_output.txt` and checked for accuracy.

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

The SQL and Python parts use the same CSV data, but they serve different purposes. SQL gives the raw totals, while pandas cleans the data before calculating the final results.

- The SQL raw revenue (99,860.20) is compared with the cleaned pandas revenue (97,358.30). The difference of 2,501.90 is exactly the value of the 5 duplicate orders.
- The narrator uses the numbers from `findings.json` rather than calculating or inventing figures of its own.

## Main results

- Cleaned revenue: Rs 97,358.30 (175 orders after removing 5 duplicates)
- Return rate: COD 44.4%, UPI 18.9%, Card 14.7%
- Highest risk segment: COD orders in Tier-2 cities, 54.5% returns
- January only looked like the best month because of two bulk orders (25 and 30 units). After removing them, March is the real peak month with Rs 20,318.90
- Discount and returns are not related (correlation about -0.09)

These results helped me see why it is important to clean the data before drawing conclusions. For example, January initially looked like the strongest month, but the two bulk orders affected the comparison. The return rates also show that COD orders deserve closer attention, especially in Tier-2 cities.

## Why I made these choices

- **Duplicates:** I found 5 duplicate orders (O0176 to O0180) that matched earlier orders in every column except `order_id`. I treated them as double-submits and removed them before filling in missing values.
- **Missing values:** I treated a blank discount as no discount and replaced it with 0. For missing ratings, I used the median because it is less affected by unusually high or low values.
- **Outliers:** I used the IQR rule to flag quantities that were far from the middle of the data. I kept these rows in the cleaned dataset rather than deleting them. I removed the two bulk orders only when plotting the monthly trend so they would not make January look like the best month.
- **Numbers:** I wanted the results to come from the data rather than manual entries. That is why `findings.json`, the charts and the narrator prompt are built from computed values.
- **Narrator:** I set the temperature to 0 to make the report more repeatable and used a 30 second timeout (in milliseconds). I also included an offline template so the project can run without an API key. The accuracy checker checks that 5 key figures appear in the report.

## Note on sample_output.txt

`sample_output.txt` contains the narrative generated by Gemini (model `gemini-3.6-flash`) and checked by the accuracy checker, with all 5 figures passing. When `generate_narrative.py` runs successfully with a `GEMINI_API_KEY`, the file is overwritten with the new Gemini response. Without a key, the script uses the offline narrative instead.
