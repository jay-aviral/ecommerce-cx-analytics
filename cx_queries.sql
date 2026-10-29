-- E-commerce CX Analytics: SQL queries (SQLite / PostgreSQL / SQL Server compatible with minor tweaks)
-- Tables: customers, orders, tickets, surveys

-- 1. HEADLINE KPIs
-- CSAT % = share of 4-5 ratings. NPS = %Promoters(9-10) minus %Detractors(0-6)
SELECT
  ROUND(100.0 * SUM(CASE WHEN csat_score >= 4 THEN 1 ELSE 0 END) / COUNT(*), 1) AS csat_pct,
  ROUND(AVG(csat_score), 2) AS avg_csat,
  ROUND(100.0 * SUM(CASE WHEN nps_score >= 9 THEN 1 ELSE 0 END) / COUNT(*)
      - 100.0 * SUM(CASE WHEN nps_score <= 6 THEN 1 ELSE 0 END) / COUNT(*), 1) AS nps
FROM surveys;

-- 2. COMPLAINT RATE, FCR, RESOLUTION TIME
SELECT
  ROUND(100.0 * (SELECT COUNT(DISTINCT order_id) FROM tickets) / (SELECT COUNT(*) FROM orders), 1) AS complaint_rate_pct,
  ROUND(100.0 * AVG(first_contact_resolved), 1) AS fcr_pct,
  ROUND(AVG(resolution_hours), 1) AS avg_resolution_hrs,
  ROUND(100.0 * AVG(CASE WHEN contact_count > 1 THEN 1.0 ELSE 0 END), 1) AS repeat_contact_pct
FROM tickets;

-- 3. COMPLAINTS BY ISSUE CATEGORY (Pareto)
SELECT issue_category,
       COUNT(*) AS tickets,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_tickets,
       ROUND(AVG(resolution_hours), 1) AS avg_res_hrs,
       ROUND(100.0 * AVG(first_contact_resolved), 1) AS fcr_pct
FROM tickets
GROUP BY issue_category
ORDER BY tickets DESC;

-- 4. LATE DELIVERY vs CSAT
SELECT o.is_late,
       COUNT(*) AS responses,
       ROUND(AVG(s.csat_score), 2) AS avg_csat,
       ROUND(100.0 * SUM(CASE WHEN s.csat_score >= 4 THEN 1 ELSE 0 END) / COUNT(*), 1) AS csat_pct
FROM surveys s JOIN orders o ON o.order_id = s.order_id
GROUP BY o.is_late;

-- 4b. CSAT by number of delay days
SELECT CASE WHEN o.delay_days = 0 THEN '0 (on time)'
            WHEN o.delay_days <= 2 THEN '1-2'
            WHEN o.delay_days <= 4 THEN '3-4' ELSE '5+' END AS delay_band,
       COUNT(*) AS responses, ROUND(AVG(s.csat_score), 2) AS avg_csat
FROM surveys s JOIN orders o ON o.order_id = s.order_id
GROUP BY 1 ORDER BY MIN(o.delay_days);

-- 5. SEGMENT FRICTION: customer segment x city tier
SELECT c.segment, c.city_tier,
       COUNT(DISTINCT o.order_id) AS orders,
       ROUND(100.0 * AVG(o.is_late), 1) AS late_pct,
       ROUND(100.0 * COUNT(DISTINCT t.order_id) / COUNT(DISTINCT o.order_id), 1) AS complaint_rate_pct
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
LEFT JOIN tickets t ON t.order_id = o.order_id
GROUP BY c.segment, c.city_tier
ORDER BY complaint_rate_pct DESC;

-- 6. CARRIER PERFORMANCE
SELECT o.carrier,
       COUNT(*) AS orders,
       ROUND(100.0 * AVG(o.is_late), 1) AS late_pct,
       ROUND(AVG(s.csat_score), 2) AS avg_csat
FROM orders o LEFT JOIN surveys s ON s.order_id = o.order_id
GROUP BY o.carrier ORDER BY late_pct DESC;

-- 7. MONTHLY TREND (SQLite strftime; use FORMAT/DATE_TRUNC elsewhere)
SELECT strftime('%Y-%m', s.survey_date) AS month,
       ROUND(100.0 * SUM(CASE WHEN s.csat_score >= 4 THEN 1 ELSE 0 END) / COUNT(*), 1) AS csat_pct,
       ROUND(100.0 * SUM(CASE WHEN s.nps_score >= 9 THEN 1 ELSE 0 END) / COUNT(*)
           - 100.0 * SUM(CASE WHEN s.nps_score <= 6 THEN 1 ELSE 0 END) / COUNT(*), 1) AS nps
FROM surveys s GROUP BY 1 ORDER BY 1;

-- 8. REPEAT-CONTACT IMPACT ON CSAT
SELECT t.contact_count, COUNT(*) AS n, ROUND(AVG(s.csat_score), 2) AS avg_csat
FROM tickets t JOIN surveys s ON s.order_id = t.order_id
GROUP BY t.contact_count ORDER BY t.contact_count;

-- 9. HIGH-FRICTION CUSTOMERS: 2+ tickets and CSAT <= 2 (window + CTE)
WITH cust AS (
  SELECT customer_id, COUNT(*) AS tickets, SUM(CASE WHEN contact_count > 1 THEN 1 ELSE 0 END) AS repeat_tickets
  FROM tickets GROUP BY customer_id
), low AS (
  SELECT customer_id, MIN(csat_score) AS min_csat FROM surveys GROUP BY customer_id
)
SELECT c.customer_id, c.tickets, c.repeat_tickets, l.min_csat
FROM cust c JOIN low l USING (customer_id)
WHERE c.tickets >= 2 AND l.min_csat <= 2
ORDER BY c.tickets DESC LIMIT 25;
