
## 🧱 Data model

Star schema with **orders** as the central table.

| Table | Rows | Key columns |
|---|---|---|
| `customers` | 8,000 | customer_id, segment, city_tier, region, acquisition_channel |
| `orders` | 30,000 | order_id, customer_id, category, carrier, delay_days, is_late, order_status |
| `tickets` | 4,758 | ticket_id, order_id, issue_category, contact_channel, first_contact_resolved, contact_count, resolution_hours |
| `surveys` | 12,203 | survey_id, order_id, csat_score, nps_score, feedback_theme |

> ⚠️ **Data note:** The dataset is **synthetic**, generated with realistic drivers built in (for example, late delivery lowers CSAT). Effect sizes are illustrative and real data would likely show weaker patterns. The pipeline works unchanged on real data with the same columns.

---

## 🛠️ Tech stack and methods

- **SQL**: KPI logic, joins, CTEs, window functions, segment and carrier analysis
- **Python** (pandas, NumPy, scikit-learn): correlation analysis, logistic regression to rank drivers of low CSAT
- **Power BI**: star-schema model, DAX measures, Pareto chart, decomposition tree, key influencers
- **Excel**: quick validation and pivot checks

## ▶️ How to run

```bash
pip install pandas numpy scikit-learn
python generate_data.py
python analysis.py
```

Then open **Power BI Desktop**, load the four CSVs from `data/`, and follow [`POWERBI_GUIDE.md`](POWERBI_GUIDE.md) to build the dashboard (5 pages: Overview, Delivery Impact, Complaints & Support, Customer Segments, Recommendations).

## 🚀 Possible next steps

- Replace the synthetic data with a real dataset (for example, Olist on Kaggle)
- Add sentiment analysis on free-text feedback
- Build a churn-risk model using CSAT, repeat contacts and delays
- Automate the refresh with a scheduled pipeline

---

## 👤 Author

**Jay** · Data analytics enthusiast
🔗 [GitHub](https://github.com/jay-aviral)
EOF