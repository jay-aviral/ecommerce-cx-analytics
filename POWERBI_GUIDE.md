# E-commerce CX Analytics — Power BI Build Guide

Dataset: 8,000 customers · 30,000 orders · 4,758 tickets · 12,203 survey responses (Oct 2025 – Oct 2026, synthetic).
Replace the CSVs in `data/` with real data later; the model and DAX stay the same.

---

## 1. Load data (Power BI Desktop)

1. Home → Get Data → Text/CSV → load all 4 files from `data/`.
2. In Power Query set types: dates → Date, scores/counts → Whole Number, `order_value`/`resolution_hours` → Decimal.
3. Add a **Date table** (Modeling → New table):

```DAX
DimDate =
ADDCOLUMNS (
    CALENDAR ( DATE ( 2025, 10, 1 ), DATE ( 2026, 12, 31 ) ),
    "Year", YEAR ( [Date] ),
    "Month No", MONTH ( [Date] ),
    "Month", FORMAT ( [Date], "MMM YYYY" ),
    "Month Sort", YEAR ( [Date] ) * 100 + MONTH ( [Date] )
)
```
Sort `Month` by `Month Sort`.

## 2. Data model (star schema)

| From (many) | To (one) | Key | Direction |
|---|---|---|---|
| orders | customers | customer_id | Single |
| tickets | orders | order_id | Single |
| surveys | orders | order_id | Single |
| orders[order_date] | DimDate[Date] | date | Single |

- Make **orders** the central fact table. Filter customers/orders → tickets and surveys.
- Hide key columns in report view.
- Mark `DimDate` as date table.

## 3. DAX measures

```DAX
-- Volumes
Total Orders        = COUNTROWS ( orders )
Total Tickets       = COUNTROWS ( tickets )
Survey Responses    = COUNTROWS ( surveys )

-- CSAT
Avg CSAT            = AVERAGE ( surveys[csat_score] )
CSAT %              = DIVIDE ( COUNTROWS ( FILTER ( surveys, surveys[csat_score] >= 4 ) ), [Survey Responses] )

-- NPS
Promoters %         = DIVIDE ( COUNTROWS ( FILTER ( surveys, surveys[nps_score] >= 9 ) ), [Survey Responses] )
Detractors %        = DIVIDE ( COUNTROWS ( FILTER ( surveys, surveys[nps_score] <= 6 ) ), [Survey Responses] )
NPS                 = ( [Promoters %] - [Detractors %] ) * 100

-- Complaints and support
Complaint Rate      = DIVIDE ( DISTINCTCOUNT ( tickets[order_id] ), [Total Orders] )
FCR %               = AVERAGE ( tickets[first_contact_resolved] )
Repeat Contact %    = DIVIDE ( COUNTROWS ( FILTER ( tickets, tickets[contact_count] > 1 ) ), [Total Tickets] )
Avg Resolution Hrs  = AVERAGE ( tickets[resolution_hours] )

-- Delivery
Late Delivery %     = AVERAGE ( orders[is_late] )
Avg Delay Days      = AVERAGE ( orders[delay_days] )

-- Root-cause comparisons
CSAT Late Orders    = CALCULATE ( [Avg CSAT], orders[is_late] = 1 )
CSAT On-time Orders = CALCULATE ( [Avg CSAT], orders[is_late] = 0 )
CSAT Gap (Late vs On-time) = [CSAT Late Orders] - [CSAT On-time Orders]

-- Targets (edit as needed) and variance
CSAT Target = 0.80
NPS Target  = 20
CSAT vs Target = [CSAT %] - [CSAT Target]

-- Month-over-month
CSAT % MoM =
VAR cur  = [CSAT %]
VAR prev = CALCULATE ( [CSAT %], DATEADD ( DimDate[Date], -1, MONTH ) )
RETURN cur - prev

-- Pareto cumulative % (use with Issue Category on axis, sorted by Total Tickets desc)
Cumulative Ticket % =
VAR cur = [Total Tickets]
RETURN
DIVIDE (
    CALCULATE ( [Total Tickets], FILTER ( ALL ( tickets[issue_category] ), [Total Tickets] >= cur ) ),
    CALCULATE ( [Total Tickets], ALL ( tickets[issue_category] ) )
)
```

Calculated columns (Modeling → New column on `orders`):
```DAX
Delay Band =
SWITCH ( TRUE (),
    orders[delay_days] = 0, "On time",
    orders[delay_days] <= 2, "1-2 days",
    orders[delay_days] <= 4, "3-4 days",
    "5+ days" )
```

## 4. Report pages and visuals

### Page 1 — Executive Overview
- KPI cards: CSAT %, NPS, Complaint Rate, FCR %, Avg Resolution Hrs, Repeat Contact %
- Line chart: CSAT % and NPS by Month
- Slicers: Month, Segment, City Tier, Region, Category

### Page 2 — Delivery Impact
- Column chart: Avg CSAT by `Delay Band` (the "late delivery kills CSAT" story)
- Clustered bar: Late Delivery % and Avg CSAT by Carrier
- Scatter: Late Delivery % (x) vs Avg CSAT (y) by City Tier and Carrier
- Card: CSAT Gap (Late vs On-time)

### Page 3 — Complaints and Support
- Pareto: columns = Total Tickets by Issue Category, line = Cumulative Ticket %
- Matrix: Issue Category x (Tickets, FCR %, Avg Resolution Hrs, Avg CSAT)
- Column chart: Avg CSAT by Contact Count (1-4)
- Bar: Tickets by Contact Channel

### Page 4 — Customer Segments / Friction
- Matrix heatmap: Segment (rows) x City Tier (cols), value = Complaint Rate (conditional formatting)
- Bar: Complaint Rate by Acquisition Channel
- Decomposition tree: Avg CSAT, explain by Segment, City Tier, Carrier, Category
- Key influencers visual: analyze "csat_score is low" (use a calculated column `Low CSAT = IF(surveys[csat_score]<=2,1,0)`)

### Page 5 — Recommendations
- Text boxes with the prioritized actions in section 6, each tied to the KPI it should move.

Design tips: 1 colour for "good", 1 for "bad" (e.g. teal vs red), grey for context; consistent KPI card layout; sync slicers across pages.

---

## 5. Key findings (from the generated data)

| # | Finding | Evidence |
|---|---|---|
| 1 | **Late delivery is the #1 driver of low CSAT** | CSAT 4.13 on-time vs 2.44 late; correlation with delay days r = -0.70 |
| 2 | CSAT falls steadily with delay length | 4.13 (on time) → 3.15 (1-2 days) → 2.44 (3-4) → 1.96 (5+) |
| 3 | Delivery-related issues dominate complaints | Late Delivery + Order Tracking = 47% of tickets |
| 4 | Refund, Damaged, Wrong Item are slowest and hardest to fix | ~94-97 hrs resolution vs ~36 hrs; FCR ~50% vs ~74% |
| 5 | Repeat contact compounds dissatisfaction | CSAT 3.07 (1 contact) → 1.68 (4 contacts); 34% of tickets need 2+ contacts |
| 6 | QuickShip is the weakest carrier | 30.4% late vs 15.0% for EcoExpress; lowest CSAT (3.61) |
| 7 | Highest friction: New customers in Tier 3 cities | 20.5% complaint rate, 27.8% late vs 11.9% for Loyal Tier 1 |
| 8 | Overall CX is weak | CSAT 70.1%, NPS -12, FCR 66.1%, 20.8% orders late |

Note: data is synthetic with built-in drivers, so the effect sizes are illustrative. With real data, expect weaker correlations, and say so in your write-up.

## 6. Prioritized recommendations

| Priority | Action | Targets | Impact | Effort |
|---|---|---|---|---|
| 1 | Renegotiate SLA or shift volume away from QuickShip, especially for Tier 3 | Late %, CSAT | High | Medium |
| 2 | Proactive delay alerts (SMS/app) plus auto-credit for delays of 3+ days | CSAT, Order Tracking tickets | High | Low |
| 3 | Add regional warehouses / dark stores for Tier 2-3 cities | Late %, complaint rate | High | High |
| 4 | Fast-track queue for refund, damaged and wrong-item tickets with agent empowerment (approve without escalation) | FCR, resolution time | High | Medium |
| 5 | Self-service live tracking and refund-status page | Tracking tickets (20%) | Medium | Medium |
| 6 | First-order onboarding: delivery-promise buffer and follow-up for new customers | New-customer CSAT, NPS | Medium | Low |
| 7 | Alert on a 2nd contact for the same ticket and route it to senior agents | Repeat-contact %, CSAT | Medium | Low |
| 8 | Pre-dispatch quality checks and better packaging for Electronics | Damaged-item tickets | Medium | Medium |

Prioritize by impact vs effort: do 2, 6 and 7 first (quick wins), 1 and 4 next (largest measurable lift), 3 as the long-term investment.

## 7. Resume / interview talking points
- "Built an end-to-end CX analytics pipeline: SQL for KPI logic, Python for root-cause analysis, Power BI for a 5-page dashboard."
- "Quantified that delivery delays cut CSAT by about 1.7 points and drive about 47% of complaints; recommended carrier SLA changes and proactive delay alerts."
- Be ready to explain: CSAT vs NPS formulas, FCR, Pareto analysis, star schema, and why you used a regression on a low-CSAT flag.
