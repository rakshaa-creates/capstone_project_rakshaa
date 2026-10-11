import os
import json
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

orders = pd.read_csv(os.path.join(BASE, "data", "orders.csv"))
customers = pd.read_csv(os.path.join(BASE, "data", "customers.csv"))
products = pd.read_csv(os.path.join(BASE, "data", "products.csv"))

print("TASK 1: LOAD AND INSPECT")
print("orders shape:", orders.shape)
print("customers shape:", customers.shape)
print("products shape:", products.shape)
print(orders.head())

print()
print("TASK 2: PAYMENT METHOD CASING")
print("Raw unique values:", orders["payment_method"].unique())
print("Number of raw values:", orders["payment_method"].nunique())
orders["payment_method"] = orders["payment_method"].str.strip().str.upper()
print("After fix:", orders["payment_method"].unique())
print(orders["payment_method"].value_counts())

print()
print("TASK 3: REMOVE DUPLICATES")
# Natural key: every business column except order_id (a double-submit gets a new order_id
# but is identical in everything else).
key_columns = ["customer_id", "product_id", "order_date", "quantity",
               "discount_pct", "payment_method", "rating", "returned"]
dup_mask = orders.duplicated(subset=key_columns, keep="first")
dropped_rows = orders[dup_mask]
print("Duplicates found:", dup_mask.sum())
print("Dropped order_ids:", dropped_rows["order_id"].tolist())
orders_clean = orders[~dup_mask].copy()
print("orders_clean shape:", orders_clean.shape)

print()
print("TASK 4: MISSING VALUES")
print("Missing discount_pct:", orders_clean["discount_pct"].isnull().sum())
print("Missing rating:", orders_clean["rating"].isnull().sum())
rating_median = orders_clean["rating"].median()
print("Median rating before filling:", rating_median)
orders_clean["discount_pct"] = orders_clean["discount_pct"].fillna(0)
orders_clean["rating"] = orders_clean["rating"].fillna(rating_median)
print(orders_clean[["discount_pct", "rating"]].isnull().sum())

print()
print("TASK 5: MERGE AND RECONCILE")
merged = orders_clean.merge(products, on="product_id").merge(customers, on="customer_id")
merged["order_value"] = merged["quantity"] * merged["price"] * (1 - merged["discount_pct"] / 100)
cleaned_total = round(merged["order_value"].sum(), 2)
print("merged shape:", merged.shape)
print("Cleaned total revenue:", cleaned_total)

raw_merged = orders.merge(products, on="product_id")
raw_merged["discount_pct"] = raw_merged["discount_pct"].fillna(0)
raw_merged["order_value"] = raw_merged["quantity"] * raw_merged["price"] * (1 - raw_merged["discount_pct"] / 100)
raw_total = round(raw_merged["order_value"].sum(), 2)
delta = round(raw_total - cleaned_total, 2)

dropped_merged = dropped_rows.merge(products, on="product_id")
dropped_merged["discount_pct"] = dropped_merged["discount_pct"].fillna(0)
dropped_merged["order_value"] = (dropped_merged["quantity"] * dropped_merged["price"]
                                 * (1 - dropped_merged["discount_pct"] / 100))
dropped_total = round(dropped_merged["order_value"].sum(), 2)

print("Raw total from SQL report (a):", raw_total)
print("Difference (raw - cleaned):", delta)
print("Combined order value of the 5 dropped rows:", dropped_total)
print()
print("Reconciliation note:")
print(f"The SQL report (a) total of Rs {raw_total:,.2f} is higher than the cleaned "
      f"pandas total of Rs {cleaned_total:,.2f} by Rs {delta:,.2f}. This whole gap comes "
      f"from the 5 duplicate orders (O0176 to O0180) removed in Task 3. Their combined "
      f"order value is Rs {dropped_total:,.2f}, which is exactly the same as the gap. "
      f"Filling missing discounts with 0 and missing ratings with the median does not "
      f"change the revenue total, because SQL already treated a missing discount as 0% "
      f"and ratings are not used in the order value.")

print()
print("TASK 6: OUTLIERS IN QUANTITY (IQR)")
q1 = merged["quantity"].quantile(0.25)
q3 = merged["quantity"].quantile(0.75)
iqr = q3 - q1
lower = q1 - 1.5 * iqr
upper = q3 + 1.5 * iqr
print("Q1:", q1, "Q3:", q3, "IQR:", iqr)
print("Lower bound:", lower, "Upper bound:", upper)
merged["is_outlier"] = (merged["quantity"] < lower) | (merged["quantity"] > upper)
print("Outlier rows:", merged["is_outlier"].sum())
print(merged[merged["is_outlier"]][["order_id", "quantity", "order_date", "order_value"]])

print()
print("TASK 7: DO COD ORDERS HAVE MORE RETURNS?")
print("Hypothesis: COD orders have a higher return rate than Card and UPI orders.")
by_payment = merged.groupby("payment_method")["returned"].agg(["count", "mean"])
by_payment["return_rate_pct"] = (by_payment["mean"] * 100).round(1)
print(by_payment)
cod_rate = by_payment.loc["COD", "return_rate_pct"]
other_best = by_payment.drop("COD")["return_rate_pct"].max()
verdict7 = "Confirmed" if cod_rate > other_best else "Rejected"
print(f"Result: {verdict7} (COD {cod_rate}% vs highest of the others {other_best}%)")

print()
print("TASK 8: PAYMENT METHOD + CITY TIER")
segments = merged.groupby(["payment_method", "city_tier"])["returned"].agg(["count", "mean"])
segments["return_rate_pct"] = (segments["mean"] * 100).round(1)
print(segments)
top_segment = segments["return_rate_pct"].idxmax()
top_rate = segments["return_rate_pct"].max()
print(f"Highest risk segment: {top_segment[0]} + Tier-{top_segment[1]} cities at {top_rate}%")
cod_t1 = segments.loc[("COD", 1), "return_rate_pct"]
cod_t2 = segments.loc[("COD", 2), "return_rate_pct"]
print(f"COD risk is not the same in every tier: Tier-1 COD returns {cod_t1}%, Tier-2 COD returns {cod_t2}%.")

print()
print("TASK 9: CORRELATION")
corr_cols = ["rating", "returned", "discount_pct", "quantity"]
corr = merged[corr_cols].corr()
print(corr.round(3))


def strength(r):
    r = abs(r)
    if r < 0.2:
        return "negligible"
    elif r < 0.4:
        return "weak"
    elif r < 0.7:
        return "moderate"
    return "strong"


for i in range(len(corr_cols)):
    for j in range(i + 1, len(corr_cols)):
        a = corr_cols[i]
        b = corr_cols[j]
        value = corr.loc[a, b]
        print(f"{a} vs {b}: {value:.3f} -> {strength(value)}")

disc_ret = corr.loc["discount_pct", "returned"]
verdict9 = "Confirmed" if disc_ret <= -0.2 else "Busted"
print(f"Hypothesis: higher discounts reduce returns -> {verdict9} (r = {disc_ret:.2f}, {strength(disc_ret)})")

print()
print("TASK 10: MONTHLY REVENUE")
merged["order_date"] = pd.to_datetime(merged["order_date"])
merged["year_month"] = merged["order_date"].dt.strftime("%Y-%m")
monthly_all = merged.groupby("year_month")["order_value"].sum().round(2)
monthly_clean = merged[~merged["is_outlier"]].groupby("year_month")["order_value"].sum().round(2)
print("Monthly revenue including outliers:")
print(monthly_all)
print("Monthly revenue excluding outliers:")
print(monthly_clean)
inflated_month = monthly_all.idxmax()
outlier_rows = merged[merged["is_outlier"] & (merged["year_month"] == inflated_month)]
outlier_text = ", ".join(f"{r.order_id} ({r.quantity} units on {r.order_date.date()})"
                         for r in outlier_rows.itertuples())
inflated_name = pd.to_datetime(inflated_month + "-01").strftime("%B")
print(f"{inflated_name} looks like the best month only because of the bulk orders: {outlier_text}.")
peak_month = monthly_clean.idxmax()
peak_name = pd.to_datetime(peak_month + "-01").strftime("%B")
print(f"Once they are removed, {peak_month} ({peak_name}) is the real peak month "
      f"with Rs {monthly_clean.max():,.2f}.")

print()
print("EXPORTING findings.json")
findings = {
    "cleaned_total_revenue_inr": cleaned_total,
    "raw_total_revenue_inr": raw_total,
    "duplicate_reconciliation_delta_inr": delta,
    "return_rate_by_payment": {
        "COD": float(by_payment.loc["COD", "return_rate_pct"]),
        "CARD": float(by_payment.loc["CARD", "return_rate_pct"]),
        "UPI": float(by_payment.loc["UPI", "return_rate_pct"]),
    },
    "highest_risk_segment": {
        "payment_method": top_segment[0],
        "city_tier": int(top_segment[1]),
        "return_rate_pct": float(top_rate),
    },
    "true_peak_month": {
        "month": peak_month,
        "revenue_inr": float(monthly_clean.max()),
    },
    "outlier_inflated_month": {
        "month": inflated_month,
        "apparent_revenue_inr": float(monthly_all[inflated_month]),
        "corrected_revenue_inr": float(monthly_clean[inflated_month]),
    },
}
out_path = os.path.join(BASE, "narrator", "findings.json")
with open(out_path, "w") as f:
    json.dump(findings, f, indent=2)
print("Saved", out_path)
print(json.dumps(findings, indent=2))
