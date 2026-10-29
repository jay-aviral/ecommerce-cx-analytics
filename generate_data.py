"""Generate a synthetic e-commerce Customer Experience dataset.
Tables: customers, orders, tickets, surveys
Built-in drivers (so root-cause analysis has real signal):
  - Late delivery lowers CSAT strongly
  - Tier-3 cities and carrier 'QuickShip' have more delays
  - Damaged/wrong item and refund issues hurt CSAT most
  - New customers and repeat contacts have more friction
"""
import numpy as np
import pandas as pd
import os

rng = np.random.default_rng(42)
OUT = "data"
os.makedirs(OUT, exist_ok=True)

N_CUST, N_ORD = 8000, 30000

# ---------- customers ----------
segments = rng.choice(["New", "Returning", "Loyal"], N_CUST, p=[0.40, 0.38, 0.22])
city_tier = rng.choice(["Tier 1", "Tier 2", "Tier 3"], N_CUST, p=[0.35, 0.37, 0.28])
region = rng.choice(["North", "South", "East", "West"], N_CUST, p=[0.24, 0.30, 0.18, 0.28])
channel = rng.choice(["Organic", "Paid Ads", "Referral", "Social"], N_CUST, p=[0.35, 0.30, 0.15, 0.20])
customers = pd.DataFrame({
    "customer_id": [f"C{i:05d}" for i in range(1, N_CUST + 1)],
    "segment": segments, "city_tier": city_tier, "region": region,
    "acquisition_channel": channel,
})

# ---------- orders ----------
cust_idx = rng.integers(0, N_CUST, N_ORD)
c = customers.iloc[cust_idx].reset_index(drop=True)
order_date = pd.to_datetime("2025-10-01") + pd.to_timedelta(rng.integers(0, 365, N_ORD), unit="D")
category = rng.choice(["Electronics", "Fashion", "Home & Kitchen", "Beauty", "Grocery", "Books"],
                      N_ORD, p=[0.20, 0.27, 0.18, 0.12, 0.15, 0.08])
carrier = rng.choice(["QuickShip", "SwiftCourier", "EcoExpress", "MetroPost"], N_ORD, p=[0.28, 0.32, 0.22, 0.18])
payment = rng.choice(["UPI", "Card", "COD", "Wallet"], N_ORD, p=[0.42, 0.25, 0.25, 0.08])
base_val = {"Electronics": 9000, "Fashion": 1800, "Home & Kitchen": 2500, "Beauty": 900, "Grocery": 700, "Books": 450}
order_value = np.array([rng.gamma(2.5, base_val[x] / 2.5) for x in category]).round(0)

promised_days = rng.integers(3, 8, N_ORD)
p_late = (0.10 + 0.12 * (c.city_tier == "Tier 3") + 0.05 * (c.city_tier == "Tier 2")
          + 0.14 * (carrier == "QuickShip") - 0.03 * (carrier == "EcoExpress")
          + 0.04 * (category == "Electronics")
          + 0.06 * pd.Series(order_date).dt.month.isin([10, 11, 12]).values)  # festive season
p_late = np.clip(p_late, 0.02, 0.7)
is_late = rng.random(N_ORD) < p_late
delay_days = np.where(is_late, rng.integers(1, 8, N_ORD), 0)
delivery_days = promised_days + delay_days - np.where(~is_late, rng.integers(0, 2, N_ORD), 0)
delivery_days = np.maximum(delivery_days, 1)

status = rng.choice(["Delivered", "Returned", "Cancelled"], N_ORD, p=[0.89, 0.07, 0.04])
orders = pd.DataFrame({
    "order_id": [f"O{i:06d}" for i in range(1, N_ORD + 1)],
    "customer_id": c.customer_id, "order_date": order_date, "category": category,
    "carrier": carrier, "payment_method": payment, "order_value": order_value,
    "promised_days": promised_days, "delivery_days": delivery_days,
    "delay_days": delay_days, "is_late": is_late.astype(int), "order_status": status,
})
orders["delivered_date"] = orders.order_date + pd.to_timedelta(orders.delivery_days, unit="D")

# ---------- tickets ----------
issues = ["Late Delivery", "Damaged Item", "Wrong Item", "Refund Delay", "Payment Failure",
          "Product Quality", "Order Tracking", "App/Website Issue"]
base_p = 0.07
p_ticket = (base_p + 0.30 * is_late + 0.05 * (status == "Returned")
            + 0.04 * (c.segment == "New") + 0.02 * (category == "Electronics"))
p_ticket = np.clip(p_ticket, 0, 0.9)
has_ticket = rng.random(N_ORD) < p_ticket
t_orders = orders[has_ticket].reset_index(drop=True)
t_c = c[has_ticket].reset_index(drop=True)
t_late = is_late[has_ticket]

def pick_issue(late, ret):
    if late:
        w = [0.50, 0.04, 0.04, 0.05, 0.02, 0.03, 0.28, 0.04]
    elif ret:
        w = [0.01, 0.25, 0.20, 0.30, 0.02, 0.17, 0.02, 0.03]
    else:
        w = [0.02, 0.14, 0.12, 0.14, 0.14, 0.18, 0.12, 0.14]
    return rng.choice(issues, p=np.array(w) / sum(w))

t_issue = [pick_issue(l, r == "Returned") for l, r in zip(t_late, t_orders.order_status)]
t_channel = rng.choice(["Chat", "Email", "Phone", "Social Media"], len(t_orders), p=[0.40, 0.25, 0.25, 0.10])
priority = rng.choice(["Low", "Medium", "High"], len(t_orders), p=[0.35, 0.45, 0.20])

hard = {"Refund Delay", "Wrong Item", "Damaged Item", "Payment Failure"}
p_fcr = np.array([0.52 if i in hard else 0.74 for i in t_issue]) - 0.08 * (t_channel == "Email") + 0.05 * (t_channel == "Chat")
fcr = rng.random(len(t_orders)) < np.clip(p_fcr, 0.1, 0.95)
contact_count = np.where(fcr, 1, rng.choice([2, 3, 4], len(t_orders), p=[0.58, 0.28, 0.14]))
res_base = np.array([60 if i in hard else 26 for i in t_issue], dtype=float)
res_hours = (res_base * rng.lognormal(0, 0.45, len(t_orders)) * (1 + 0.5 * (contact_count - 1)) *
             np.where(t_channel == "Email", 1.4, 1.0) * np.where(priority == "High", 0.7, 1.0)).round(1)
created = t_orders.delivered_date + pd.to_timedelta(rng.integers(0, 4, len(t_orders)), unit="D")
tickets = pd.DataFrame({
    "ticket_id": [f"T{i:06d}" for i in range(1, len(t_orders) + 1)],
    "order_id": t_orders.order_id, "customer_id": t_orders.customer_id,
    "created_date": created, "issue_category": t_issue, "contact_channel": t_channel,
    "priority": priority, "first_contact_resolved": fcr.astype(int),
    "contact_count": contact_count, "resolution_hours": res_hours,
})
tickets["resolved_date"] = tickets.created_date + pd.to_timedelta(tickets.resolution_hours, unit="h")

# ---------- surveys ----------
resp = rng.random(N_ORD) < 0.42
s_orders = orders[resp & (status != "Cancelled")].reset_index(drop=True)
s_c = c[resp & (status != "Cancelled")].reset_index(drop=True)
tk = tickets.set_index("order_id")
has_t = s_orders.order_id.isin(tk.index).values
t_issue_map = tk.issue_category.to_dict()
t_contact_map = tk.contact_count.to_dict()
t_fcr_map = tk.first_contact_resolved.to_dict()
severe = {"Damaged Item": 0.9, "Wrong Item": 0.8, "Refund Delay": 0.8, "Payment Failure": 0.4, "Product Quality": 0.6}

score = np.full(len(s_orders), 4.35)
score -= 0.35 * s_orders.delay_days.clip(upper=5).values          # delay penalty
score -= 0.35 * (s_orders.delay_days.values > 0)
score -= 0.35 * (s_orders.order_status == "Returned").values
score -= 0.25 * (s_c.segment == "New").values
score -= 0.15 * (s_c.city_tier == "Tier 3").values
score += 0.15 * (s_c.segment == "Loyal").values
for k, o in enumerate(s_orders.order_id):
    if o in t_issue_map:
        score[k] -= severe.get(t_issue_map[o], 0.3)
        score[k] -= 0.45 * (t_contact_map[o] - 1)
        score[k] += 0.25 * t_fcr_map[o]
score += rng.normal(0, 0.55, len(s_orders))
csat = np.clip(np.round(score), 1, 5).astype(int)
nps = np.clip(np.round((score - 1) * 2.6 + rng.normal(0, 1.1, len(s_orders)) - 0.5), 0, 10).astype(int)
themes = np.where(csat <= 2, rng.choice(["Delivery delay", "Product condition", "Support experience", "Refund", "Price/Value"],
                                        len(s_orders), p=[0.40, 0.22, 0.15, 0.15, 0.08]),
                  np.where(csat == 3, rng.choice(["Delivery speed", "Packaging", "Support", "Price/Value"],
                                                 len(s_orders), p=[0.35, 0.2, 0.2, 0.25]),
                           rng.choice(["Fast delivery", "Product quality", "Good support", "Value for money"],
                                      len(s_orders))))
surveys = pd.DataFrame({
    "survey_id": [f"S{i:06d}" for i in range(1, len(s_orders) + 1)],
    "order_id": s_orders.order_id, "customer_id": s_orders.customer_id,
    "survey_date": s_orders.delivered_date + pd.to_timedelta(rng.integers(1, 6, len(s_orders)), unit="D"),
    "csat_score": csat, "nps_score": nps, "feedback_theme": themes,
})

customers.to_csv(f"{OUT}/customers.csv", index=False)
orders.drop(columns=[]).to_csv(f"{OUT}/orders.csv", index=False)
tickets.to_csv(f"{OUT}/tickets.csv", index=False)
surveys.to_csv(f"{OUT}/surveys.csv", index=False)
print({k: len(v) for k, v in dict(customers=customers, orders=orders, tickets=tickets, surveys=surveys).items()})
