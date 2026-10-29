"""Root-cause analysis for the CX project. Run: python analysis.py"""
import sqlite3, re
import pandas as pd, numpy as np
import os

os.makedirs("output", exist_ok=True)
con = sqlite3.connect(":memory:")
for t in ["customers", "orders", "tickets", "surveys"]:
    pd.read_csv(f"data/{t}.csv").to_sql(t, con, index=False)

# ---- 1. Validate every SQL query runs ----
sql = re.sub(r"--[^\n]*", "", open("cx_queries.sql").read())  # strip comments first
stmts = [s.strip() for s in sql.split(";") if s.strip()]
ok = 0
for s in stmts:
    pd.read_sql(s, con); ok += 1
print(f"SQL queries executed OK: {ok}/{len(stmts)}\n")

q = lambda s: pd.read_sql(s, con)

# ---- 2. KPIs ----
kpi = {
    "csat_pct": q("SELECT 100.0*AVG(csat_score>=4) v FROM surveys").v[0],
    "nps": q("SELECT 100.0*AVG(nps_score>=9)-100.0*AVG(nps_score<=6) v FROM surveys").v[0],
    "complaint_rate_pct": q("SELECT 100.0*(SELECT COUNT(DISTINCT order_id) FROM tickets)/(SELECT COUNT(*) FROM orders) v").v[0],
    "fcr_pct": q("SELECT 100.0*AVG(first_contact_resolved) v FROM tickets").v[0],
    "avg_resolution_hrs": q("SELECT AVG(resolution_hours) v FROM tickets").v[0],
    "repeat_contact_pct": q("SELECT 100.0*AVG(contact_count>1) v FROM tickets").v[0],
    "late_delivery_pct": q("SELECT 100.0*AVG(is_late) v FROM orders").v[0],
}
pd.Series(kpi).round(1).to_csv("output/kpi_summary.csv", header=["value"])
print("KPIs:\n", pd.Series(kpi).round(1), "\n")

# ---- 3. Late delivery vs CSAT ----
df = q("""SELECT s.csat_score, s.nps_score, o.is_late, o.delay_days, o.order_status, o.carrier, o.category,
                 c.segment, c.city_tier, c.region, c.acquisition_channel
          FROM surveys s JOIN orders o USING(order_id) JOIN customers c ON c.customer_id=o.customer_id""")
r = df.csat_score.corr(df.delay_days)
late = df.groupby("is_late").csat_score.agg(["mean", "count"]).round(2)
print("CSAT by late flag:\n", late, f"\nPearson r (delay_days vs CSAT) = {r:.2f}\n")
band = df.assign(band=pd.cut(df.delay_days, [-1, 0, 2, 4, 99], labels=["On time", "1-2 days", "3-4 days", "5+ days"])) \
         .groupby("band", observed=True).csat_score.agg(["mean", "count"]).round(2)
print(band, "\n")

# ---- 4. Issue categories ----
iss = q("""SELECT issue_category, COUNT(*) tickets, ROUND(AVG(resolution_hours),1) avg_res_hrs,
                  ROUND(100.0*AVG(first_contact_resolved),1) fcr_pct FROM tickets GROUP BY 1 ORDER BY 2 DESC""")
iss["pct"] = (100 * iss.tickets / iss.tickets.sum()).round(1)
iss["cum_pct"] = iss.pct.cumsum().round(1)
iss_csat = q("""SELECT t.issue_category, ROUND(AVG(s.csat_score),2) avg_csat FROM tickets t JOIN surveys s USING(order_id) GROUP BY 1""")
iss = iss.merge(iss_csat, on="issue_category")
iss.to_csv("output/issue_pareto.csv", index=False)
print(iss, "\n")

# ---- 5. Segment friction ----
seg = q("""SELECT c.segment, c.city_tier, COUNT(*) orders, ROUND(100.0*AVG(o.is_late),1) late_pct,
                  ROUND(100.0*COUNT(DISTINCT t.order_id)/COUNT(*),1) complaint_rate_pct
           FROM orders o JOIN customers c USING(customer_id) LEFT JOIN tickets t ON t.order_id=o.order_id
           GROUP BY 1,2 ORDER BY complaint_rate_pct DESC""")
seg.to_csv("output/segment_friction.csv", index=False)
print(seg, "\n")

car = q("""SELECT o.carrier, COUNT(*) orders, ROUND(100.0*AVG(o.is_late),1) late_pct, ROUND(AVG(s.csat_score),2) avg_csat
           FROM orders o LEFT JOIN surveys s USING(order_id) GROUP BY 1 ORDER BY 3 DESC""")
car.to_csv("output/carrier_perf.csv", index=False)
print(car, "\n")

# ---- 6. Driver importance (regression on low-CSAT flag) ----
from sklearn.linear_model import LogisticRegression
d = q("""SELECT (s.csat_score<=2) low, o.is_late, o.delay_days, (o.order_status='Returned') returned,
                (c.segment='New') new_cust, (c.city_tier='Tier 3') tier3,
                COALESCE(t.contact_count,0) contacts, COALESCE(t.first_contact_resolved,1) fcr,
                (t.ticket_id IS NOT NULL) has_ticket,
                COALESCE(t.issue_category IN ('Damaged Item','Wrong Item','Refund Delay'),0) severe_issue
         FROM surveys s JOIN orders o USING(order_id) JOIN customers c ON c.customer_id=o.customer_id
         LEFT JOIN tickets t ON t.order_id=o.order_id""")
X = d.drop(columns="low").astype(float)
Xs = (X - X.mean()) / X.std()
m = LogisticRegression(max_iter=1000).fit(Xs, d.low)
imp = pd.Series(m.coef_[0], index=X.columns).sort_values(ascending=False).round(2)
imp.to_csv("output/driver_importance.csv", header=["std_coefficient"])
print("Drivers of LOW CSAT (std. logistic coefficient):\n", imp, "\n")

# ---- 7. Repeat contact ----
rc = q("""SELECT t.contact_count, COUNT(*) n, ROUND(AVG(s.csat_score),2) avg_csat
          FROM tickets t JOIN surveys s USING(order_id) GROUP BY 1 ORDER BY 1""")
print(rc)
