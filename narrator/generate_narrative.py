import os
import re
import json
from datetime import datetime

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINDINGS_PATH = os.path.join(BASE, "narrator", "findings.json")
SAMPLE_PATH = os.path.join(BASE, "narrator", "sample_output.txt")
# Gemini retires models over time and some are limited to older accounts (a 404 NOT_FOUND
# means that). So we try these in order and use the first one the API key can reach.
# To force one model, set GEMINI_MODEL in the environment.
MODEL_CANDIDATES = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-2.5-flash",
]

SYSTEM_INSTRUCTION = (
    "You are a senior data analyst writing for Mamaearth's regional ops and finance heads. "
    "Write a short business narrative of about 250 words using the SCR structure with three "
    "labeled sections: Situation, Complication, Resolution. "
    "Every number you write must come from the findings supplied by the user and must keep "
    "exactly the same value. Do not invent any statistics, percentages or rupee amounts."
)


def month_name(month_text):
    return datetime.strptime(month_text, "%Y-%m").strftime("%B")


def build_prompt(findings):
    cod = findings["return_rate_by_payment"]["COD"]
    card = findings["return_rate_by_payment"]["CARD"]
    upi = findings["return_rate_by_payment"]["UPI"]
    seg = findings["highest_risk_segment"]
    peak = findings["true_peak_month"]
    jan = findings["outlier_inflated_month"]
    prompt = f"""Write the SCR narrative using only these verified findings.

Revenue:
- Cleaned total revenue: Rs {findings['cleaned_total_revenue_inr']:,.2f}
- Raw total revenue before cleaning: Rs {findings['raw_total_revenue_inr']:,.2f}
- Difference caused by duplicate orders: Rs {findings['duplicate_reconciliation_delta_inr']:,.2f}

Return rate by payment method:
- COD: {cod}%
- CARD: {card}%
- UPI: {upi}%

Highest risk segment: {seg['payment_method']} orders in Tier-{seg['city_tier']} cities with a return rate of {seg['return_rate_pct']}%.

Monthly revenue:
- True peak month: {month_name(peak['month'])} with Rs {peak['revenue_inr']:,.2f}
- {month_name(jan['month'])} looked like the best month at Rs {jan['apparent_revenue_inr']:,.2f}, but only because of two bulk orders. Without them it was Rs {jan['corrected_revenue_inr']:,.2f}.
"""
    return prompt


def generate_scr_narrative_offline(findings):
    cod = findings["return_rate_by_payment"]["COD"]
    card = findings["return_rate_by_payment"]["CARD"]
    upi = findings["return_rate_by_payment"]["UPI"]
    seg = findings["highest_risk_segment"]
    peak = findings["true_peak_month"]
    jan = findings["outlier_inflated_month"]

    narrative = f"""Situation
After removing duplicate orders, Mamaearth's cleaned total revenue is Rs {findings['cleaned_total_revenue_inr']:,.2f}. The raw order data showed Rs {findings['raw_total_revenue_inr']:,.2f}, and the difference of Rs {findings['duplicate_reconciliation_delta_inr']:,.2f} comes entirely from duplicate orders caused by a double-submit bug. {month_name(peak['month'])} is the real peak month with Rs {peak['revenue_inr']:,.2f} in revenue.

Complication
Returns are not spread evenly. Cash on Delivery orders have a return rate of {cod}%, compared with {upi}% for UPI and {card}% for Card. The problem is worst in one segment: {seg['payment_method']} orders in Tier-{seg['city_tier']} cities return at {seg['return_rate_pct']}%. Also, {month_name(jan['month'])} looked like the best month at Rs {jan['apparent_revenue_inr']:,.2f}, but that was only because of two bulk orders. Without them, {month_name(jan['month'])} revenue was Rs {jan['corrected_revenue_inr']:,.2f}.

Resolution
Ops should focus first on {seg['payment_method']} orders in Tier-{seg['city_tier']} cities, for example by confirming orders by phone or encouraging prepaid payment. Finance should report revenue after removing duplicates and bulk-order outliers, and should plan around {month_name(peak['month'])} as the true peak month. The double-submit bug should also be fixed so duplicates stop entering the data."""
    return {"status": "success", "narrative": narrative, "tokens": None}


def generate_scr_narrative(findings):
    """Call Gemini. Always returns a dict: status, narrative, tokens (and message on error)."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"status": "error", "narrative": None, "tokens": None,
                "message": "GEMINI_API_KEY is not set"}
    if genai is None:
        return {"status": "error", "narrative": None, "tokens": None,
                "message": "google-genai is not installed"}

    prompt = build_prompt(findings)
    models = [os.environ["GEMINI_MODEL"]] if os.environ.get("GEMINI_MODEL") else MODEL_CANDIDATES
    last_error = "no model tried"
    try:
        client = genai.Client(api_key=api_key)
        for model_name in models:
            try:
                # temperature 0: factual report, same numbers and wording every run.
                # max_output_tokens 4096: far above the 1024 minimum, so the text is never cut off
                # (some models also spend output tokens on internal thinking).
                # timeout is in MILLISECONDS (30000 = 30 seconds).
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        temperature=0.0,
                        max_output_tokens=4096,
                        http_options=types.HttpOptions(timeout=30000),
                    ),
                )
                if not response.text:
                    last_error = f"{model_name}: empty response"
                    continue
                return {"status": "success", "narrative": response.text, "model": model_name,
                        "tokens": response.usage_metadata.total_token_count}
            except Exception as err:
                # model missing (404), quota (429), overloaded (503)...: try the next one
                last_error = f"{model_name}: {err}"
    except Exception as err:
        last_error = str(err)
    return {"status": "error", "narrative": None, "tokens": None, "message": last_error}


def get_narrative(findings):
    """Try Gemini first; on any error fall back to the offline template."""
    result = generate_scr_narrative(findings)
    if result["status"] == "success":
        return result
    print("Gemini not used:", result["message"])
    print("Using the offline narrator instead.")
    return generate_scr_narrative_offline(findings)


def number_in_text(value, text):
    """True if the number appears as a whole number (so 44.4 does not match 144.4)."""
    for option in {f"{value:.2f}", str(value), f"{value:.1f}"}:
        if re.search(r"(?<![\d.])" + re.escape(option) + r"(?![\d])", text):
            return True
    return False


def check_narrative(text, findings):
    """Check that five key figures from findings.json appear in the narrative."""
    text = text.replace(",", "")
    peak = findings["true_peak_month"]
    checks = [
        ("cleaned total revenue", findings["cleaned_total_revenue_inr"]),
        ("COD return rate", findings["return_rate_by_payment"]["COD"]),
        ("highest risk segment rate", findings["highest_risk_segment"]["return_rate_pct"]),
        ("duplicate delta", findings["duplicate_reconciliation_delta_inr"]),
        ("peak month revenue", peak["revenue_inr"]),
    ]
    all_passed = True
    for label, value in checks:
        found = number_in_text(value, text)
        if label == "peak month revenue":
            found = found and month_name(peak["month"]) in text
        print(f"{'PASS' if found else 'FAIL'}: {label} ({value})")
        all_passed = all_passed and found
    return all_passed


if __name__ == "__main__":
    with open(FINDINGS_PATH) as f:
        findings = json.load(f)

    result = get_narrative(findings)
    print()
    print(result["narrative"])
    print()
    print("Checking this narrative:")
    check_narrative(result["narrative"], findings)

    if result["tokens"] is not None:
        # a real Gemini answer: save it as the sample output
        with open(SAMPLE_PATH, "w") as f:
            f.write(result["narrative"])
        print(f"Gemini ({result['model']}) output saved to", SAMPLE_PATH)
    elif not os.path.exists(SAMPLE_PATH):
        with open(SAMPLE_PATH, "w") as f:
            f.write(result["narrative"])
        print("Offline narrative saved to", SAMPLE_PATH)

    print()
    print("Checking saved sample_output.txt:")
    with open(SAMPLE_PATH) as f:
        check_narrative(f.read(), findings)
