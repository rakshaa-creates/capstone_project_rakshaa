import os
import pandas as pd
import matplotlib.pyplot as plt

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

orders = pd.read_csv(os.path.join(BASE, "data", "orders.csv"))
products = pd.read_csv(os.path.join(BASE, "data", "products.csv"))

orders["payment_method"] = orders["payment_method"].str.strip().str.upper()
key_columns = ["customer_id", "product_id", "order_date", "quantity",
               "discount_pct", "payment_method", "rating", "returned"]
orders = orders[~orders.duplicated(subset=key_columns, keep="first")].copy()
orders["discount_pct"] = orders["discount_pct"].fillna(0)

df = orders.merge(products, on="product_id")
df["order_value"] = df["quantity"] * df["price"] * (1 - df["discount_pct"] / 100)

os.makedirs(os.path.join(BASE, "visualizations"), exist_ok=True)

rates = (df.groupby("payment_method")["returned"].mean() * 100).round(1)
rates = rates.sort_values(ascending=False)

plt.figure(figsize=(7, 5))
bars = plt.bar(rates.index, rates.values, color=["#d9534f", "#f0ad4e", "#5bc0de"])
for bar, value in zip(bars, rates.values):
    plt.text(bar.get_x() + bar.get_width() / 2, value + 0.8, f"{value}%", ha="center")
times = round(rates["COD"] / rates["CARD"])
plt.title(f"COD Returns at {rates['COD']}% - {times}x Card")
plt.xlabel("Payment method")
plt.ylabel("Return rate (%)")
plt.ylim(0, rates.max() + 8)
plt.tight_layout()
plt.savefig(os.path.join(BASE, "visualizations", "return_rate_by_payment.png"))
plt.close()

q1 = df["quantity"].quantile(0.25)
q3 = df["quantity"].quantile(0.75)
iqr = q3 - q1
outlier = (df["quantity"] < q1 - 1.5 * iqr) | (df["quantity"] > q3 + 1.5 * iqr)
df = df[~outlier].copy()

df["year_month"] = pd.to_datetime(df["order_date"]).dt.strftime("%Y-%m")
monthly = df.groupby("year_month")["order_value"].sum().round(2)
peak = monthly.idxmax()
peak_name = pd.to_datetime(peak + "-01").strftime("%B")

plt.figure(figsize=(8, 5))
plt.plot(monthly.index, monthly.values, marker="o", color="#2a7f62")
plt.annotate(f"Peak: {monthly.max():,.0f}", (peak, monthly.max()),
             textcoords="offset points", xytext=(0, 10), ha="center")
plt.title(f"Monthly Revenue (outliers removed) - {peak_name} is the Peak Month")
plt.xlabel("Month")
plt.ylabel("Revenue (INR)")
plt.ylim(0, monthly.max() + 3000)
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig(os.path.join(BASE, "visualizations", "monthly_revenue_trend.png"))
plt.close()

print("Saved return_rate_by_payment.png and monthly_revenue_trend.png")
