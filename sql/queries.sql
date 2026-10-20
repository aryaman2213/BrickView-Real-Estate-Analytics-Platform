-- BrickView: the 30 business questions from the project brief.
-- Each query starts with "-- name: Qnn | Category | Question" and may carry a "-- chart:" hint
-- that the Streamlit "SQL Insights" page uses to draw it. src/db.load_queries() parses this file.

-- ================================================================ Property & Pricing Analysis
-- name: Q01 | Property & Pricing | What is the average listing price by city?
-- insight: New York is the priciest city ($2.49M average) and Chicago the cheapest ($2.43M), a spread of only 2.6%.
-- chart: bar x=city y=avg_list_price
SELECT city,
       COUNT(*)              AS listings,
       ROUND(AVG(price), 2)  AS avg_list_price
FROM listings
GROUP BY city
ORDER BY avg_list_price DESC;

-- name: Q02 | Property & Pricing | What is the average price per square foot by property type?
-- insight: Houses have the highest price per sq ft ($796) and condos the lowest ($755). The plain average is far above the size-weighted figure (~$480) because small units carry very high per-sq-ft prices.
-- chart: bar x=property_type y=avg_price_per_sqft
SELECT property_type,
       COUNT(*)                                AS listings,
       ROUND(AVG(price / area_sqft), 2)        AS avg_price_per_sqft,
       ROUND(SUM(price) / SUM(area_sqft), 2)   AS weighted_price_per_sqft
FROM listings
GROUP BY property_type
ORDER BY avg_price_per_sqft DESC;

-- name: Q03 | Property & Pricing | How does furnishing status impact property prices?
-- insight: Furnished homes list about 1.2% higher than unfurnished ones: a small premium.
-- chart: bar x=furnishing_status y=avg_list_price
SELECT pa.furnishing_status,
       COUNT(*)                                 AS listings,
       ROUND(AVG(l.price), 2)                   AS avg_list_price,
       ROUND(AVG(l.price / l.area_sqft), 2)     AS avg_price_per_sqft
FROM listings l
JOIN property_attributes pa ON pa.listing_id = l.listing_id
GROUP BY pa.furnishing_status
ORDER BY avg_list_price DESC;

-- name: Q04 | Property & Pricing | Do properties closer to metro stations command higher prices?
-- insight: No metro premium. Listings within 2 km of a metro average $2.38M, those 10 km+ away $2.53M. Distance does not raise prices in this data.
-- chart: bar x=metro_distance y=avg_list_price
SELECT CASE WHEN pa.metro_distance_km < 2  THEN '1. Under 2 km'
            WHEN pa.metro_distance_km < 5  THEN '2. 2-5 km'
            WHEN pa.metro_distance_km < 10 THEN '3. 5-10 km'
            ELSE '4. 10 km+' END                AS metro_distance,
       COUNT(*)                                 AS listings,
       ROUND(AVG(l.price), 2)                   AS avg_list_price,
       ROUND(AVG(l.price / l.area_sqft), 2)     AS avg_price_per_sqft
FROM listings l
JOIN property_attributes pa ON pa.listing_id = l.listing_id
GROUP BY metro_distance
ORDER BY metro_distance;

-- name: Q05 | Property & Pricing | Are rented properties priced differently from non-rented ones?
-- insight: Rented and non-rented properties are priced almost the same (+0.4% for rented).
-- chart: bar x=rental_status y=avg_list_price
SELECT CASE pa.is_rented WHEN 1 THEN 'Rented' ELSE 'Not rented' END AS rental_status,
       COUNT(*)                                 AS listings,
       ROUND(AVG(l.price), 2)                   AS avg_list_price,
       ROUND(AVG(l.price / l.area_sqft), 2)     AS avg_price_per_sqft
FROM listings l
JOIN property_attributes pa ON pa.listing_id = l.listing_id
GROUP BY pa.is_rented
ORDER BY avg_list_price DESC;

-- name: Q06 | Property & Pricing | How do bedrooms and bathrooms affect pricing?
-- insight: Bedroom and bathroom counts barely move the average price (every group sits between about $2.38M and $2.56M): size is not priced in this data set.
-- chart: bar x=bedrooms y=avg_list_price color=bathrooms
SELECT pa.bedrooms,
       pa.bathrooms,
       COUNT(*)                 AS listings,
       ROUND(AVG(l.price), 2)   AS avg_list_price
FROM listings l
JOIN property_attributes pa ON pa.listing_id = l.listing_id
GROUP BY pa.bedrooms, pa.bathrooms
ORDER BY pa.bedrooms, pa.bathrooms;

-- name: Q07 | Property & Pricing | Do properties with parking and power backup sell at higher prices?
-- insight: Homes with both parking and power backup sold for the most ($1.09M average), about 4% more than homes with neither ($1.05M).
-- chart: bar x=amenities y=avg_sale_price
SELECT CASE WHEN pa.parking_available = 1 AND pa.power_backup = 1 THEN 'Parking + power backup'
            WHEN pa.parking_available = 1 THEN 'Parking only'
            WHEN pa.power_backup = 1 THEN 'Power backup only'
            ELSE 'Neither' END                  AS amenities,
       COUNT(*)                                 AS listings,
       ROUND(AVG(l.price), 2)                   AS avg_list_price,
       COUNT(s.sale_id)                         AS sales,
       ROUND(AVG(s.sale_price), 2)              AS avg_sale_price
FROM listings l
JOIN property_attributes pa ON pa.listing_id = l.listing_id
LEFT JOIN sales s           ON s.listing_id  = l.listing_id
GROUP BY amenities
ORDER BY avg_sale_price DESC;

-- name: Q08 | Property & Pricing | How does year built influence listing price?
-- insight: No premium for new construction: homes built 1990-1994 list highest ($2.58M average), later 5-year cohorts sit between $2.37M and $2.48M.
-- chart: line x=year_built y=avg_list_price
SELECT pa.year_built,
       COUNT(*)                 AS listings,
       ROUND(AVG(l.price), 2)   AS avg_list_price
FROM listings l
JOIN property_attributes pa ON pa.listing_id = l.listing_id
GROUP BY pa.year_built
ORDER BY pa.year_built;

-- name: Q09 | Property & Pricing | Which cities have the highest average property prices?
-- insight: New York ranks first on both average ($2.49M) and median ($2.45M) price; the ranking is the same on either measure.
-- chart: bar x=city y=avg_list_price
WITH ordered AS (
    SELECT city, price,
           ROW_NUMBER() OVER (PARTITION BY city ORDER BY price) AS rn,
           COUNT(*)     OVER (PARTITION BY city)                AS n
    FROM listings
),
median AS (
    SELECT city, ROUND(AVG(price), 2) AS median_list_price
    FROM ordered
    WHERE rn IN ((n + 1) / 2, (n + 2) / 2)
    GROUP BY city
)
SELECT RANK() OVER (ORDER BY AVG(l.price) DESC) AS price_rank,
       l.city,
       ROUND(AVG(l.price), 2)  AS avg_list_price,
       m.median_list_price,
       ROUND(MAX(l.price), 2)  AS max_list_price
FROM listings l
JOIN median m ON m.city = l.city
GROUP BY l.city
ORDER BY price_rank;

-- name: Q10 | Property & Pricing | How are properties distributed across price buckets?
-- insight: Listings are spread almost evenly across the five $1M-wide buckets (19-23% each); $1M-2M is the largest.
-- chart: bar x=price_bucket y=listings
SELECT CASE WHEN price < 1000000 THEN '1. Under $1M'
            WHEN price < 2000000 THEN '2. $1M-2M'
            WHEN price < 3000000 THEN '3. $2M-3M'
            WHEN price < 4000000 THEN '4. $3M-4M'
            ELSE '5. $4M+' END                                     AS price_bucket,
       COUNT(*)                                                     AS listings,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM listings), 2) AS pct_of_listings
FROM listings
GROUP BY price_bucket
ORDER BY price_bucket;

-- ================================================================ Sales & Market Performance
-- name: Q11 | Sales & Market | What is the average days on market by city?
-- insight: Houston sells fastest (58.5 days on average) and Los Angeles slowest (65.1 days).
-- chart: bar x=city y=avg_days_on_market
SELECT l.city,
       COUNT(*)                          AS sales,
       ROUND(AVG(s.days_on_market), 1)   AS avg_days_on_market
FROM sales s
JOIN listings l ON l.listing_id = s.listing_id
GROUP BY l.city
ORDER BY avg_days_on_market;

-- name: Q12 | Sales & Market | Which property types sell the fastest?
-- insight: Houses sell fastest (58.3 days); condos take the longest (66.5 days), about 8 days more.
-- chart: bar x=property_type y=avg_days_on_market
SELECT l.property_type,
       COUNT(*)                          AS sales,
       ROUND(AVG(s.days_on_market), 1)   AS avg_days_on_market,
       MIN(s.days_on_market)             AS fastest_sale_days
FROM sales s
JOIN listings l ON l.listing_id = s.listing_id
GROUP BY l.property_type
ORDER BY avg_days_on_market;

-- name: Q13 | Sales & Market | What percentage of properties are sold above listing price?
-- insight: 49.3% of sales closed above the listing price and 50.7% below: pricing is close to fair value.
-- chart: pie names=outcome values=sales
SELECT CASE WHEN s.sale_price > l.price THEN 'Above list price'
            WHEN s.sale_price = l.price THEN 'At list price'
            ELSE 'Below list price' END                            AS outcome,
       COUNT(*)                                                     AS sales,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM sales), 2)    AS pct_of_sales
FROM sales s
JOIN listings l ON l.listing_id = s.listing_id
GROUP BY outcome
ORDER BY sales DESC;

-- name: Q14 | Sales & Market | What is the sale-to-list price ratio by city?
-- insight: Sale-to-list ratios sit within 0.2% of 1.00 in every city; Chicago is the only city slightly above list (1.0015).
-- chart: bar x=city y=avg_sale_to_list_ratio
SELECT l.city,
       COUNT(*)                                     AS sales,
       ROUND(AVG(s.sale_price / l.price), 4)        AS avg_sale_to_list_ratio,
       ROUND(SUM(s.sale_price) / SUM(l.price), 4)   AS total_sale_to_list_ratio
FROM sales s
JOIN listings l ON l.listing_id = s.listing_id
GROUP BY l.city
ORDER BY avg_sale_to_list_ratio DESC;

-- name: Q15 | Sales & Market | Which listings took more than 90 days to sell?
-- insight: 188 of 720 sales (26%) took more than 90 days; the slowest took 120 days.
SELECT s.listing_id, l.city, l.property_type, l.price AS list_price, s.sale_price,
       l.date_listed, s.date_sold, s.days_on_market
FROM sales s
JOIN listings l ON l.listing_id = s.listing_id
WHERE s.days_on_market > 90
ORDER BY s.days_on_market DESC, s.listing_id;

-- name: Q16 | Sales & Market | How does metro distance affect time on market?
-- insight: Homes within 2 km of a metro took the longest to sell (64.7 days vs about 61 elsewhere); no sold home is more than 8 km from a metro.
-- chart: bar x=metro_distance y=avg_days_on_market
SELECT CASE WHEN pa.metro_distance_km < 2  THEN '1. Under 2 km'
            WHEN pa.metro_distance_km < 5  THEN '2. 2-5 km'
            WHEN pa.metro_distance_km < 10 THEN '3. 5-10 km'
            ELSE '4. 10 km+' END            AS metro_distance,
       COUNT(*)                             AS sales,
       ROUND(AVG(s.days_on_market), 1)      AS avg_days_on_market
FROM sales s
JOIN property_attributes pa ON pa.listing_id = s.listing_id
GROUP BY metro_distance
ORDER BY metro_distance;

-- name: Q17 | Sales & Market | What is the monthly sales trend?
-- insight: Sales ramp up through 2023, peak in October 2023 (64 sales), and taper off after mid-2024.
-- chart: line x=month y=sales
SELECT strftime('%Y-%m', date_sold)   AS month,
       COUNT(*)                       AS sales,
       ROUND(SUM(sale_price), 2)      AS revenue,
       ROUND(AVG(sale_price), 2)      AS avg_sale_price
FROM sales
GROUP BY month
ORDER BY month;

-- name: Q18 | Sales & Market | Which properties are currently unsold?
-- insight: 20,480 of 21,200 listings (96.6%) are still unsold. All 720 sales come from the first 1,200 listings (L00001-L01200).
SELECT l.listing_id, l.city, l.property_type, l.price, l.area_sqft, l.date_listed, l.agent_id
FROM listings l
WHERE NOT EXISTS (SELECT 1 FROM sales s WHERE s.listing_id = l.listing_id)
ORDER BY l.date_listed, l.listing_id;

-- ================================================================ Agent Performance
-- name: Q19 | Agent Performance | Which agents have closed the most sales?
-- insight: Agent A0042 closed the most sales (25), followed by A0011 (24).
-- chart: bar x=sales_closed y=name orientation=h
SELECT a.agent_id, a.name,
       COUNT(s.sale_id) AS sales_closed
FROM agents a
JOIN listings l ON l.agent_id   = a.agent_id
JOIN sales s    ON s.listing_id = l.listing_id
GROUP BY a.agent_id
ORDER BY sales_closed DESC, a.agent_id
LIMIT 10;

-- name: Q20 | Agent Performance | Who are the top agents by total sales revenue?
-- insight: Agent A0011 generated the most revenue ($27.9M from 24 sales), just ahead of A0042 ($27.2M).
-- chart: bar x=total_revenue y=name orientation=h
SELECT a.agent_id, a.name,
       COUNT(s.sale_id)              AS sales_closed,
       ROUND(SUM(s.sale_price), 2)   AS total_revenue
FROM agents a
JOIN listings l ON l.agent_id   = a.agent_id
JOIN sales s    ON s.listing_id = l.listing_id
GROUP BY a.agent_id
ORDER BY total_revenue DESC
LIMIT 10;

-- name: Q21 | Agent Performance | Which agents close deals fastest?
-- insight: Among agents with at least 5 sales, A0044 is fastest (36.9 days on market on average).
-- chart: bar x=avg_days_on_market y=name orientation=h
SELECT a.agent_id, a.name,
       COUNT(s.sale_id)                  AS sales_closed,
       ROUND(AVG(s.days_on_market), 1)   AS avg_days_on_market,
       a.avg_closing_days                AS profile_avg_closing_days
FROM agents a
JOIN listings l ON l.agent_id   = a.agent_id
JOIN sales s    ON s.listing_id = l.listing_id
GROUP BY a.agent_id
HAVING COUNT(s.sale_id) >= 5
ORDER BY avg_days_on_market, a.agent_id
LIMIT 10;

-- name: Q22 | Agent Performance | Does experience correlate with deals closed?
-- insight: Weak positive link: agents with 21+ years average 166 lifetime deals vs 109 for 0-5 years, but the trend is not steady and sales in this data set don't follow it.
-- chart: bar x=experience y=avg_deals_closed
SELECT CASE WHEN experience_years <= 5  THEN '1. 0-5 yrs'
            WHEN experience_years <= 10 THEN '2. 6-10 yrs'
            WHEN experience_years <= 15 THEN '3. 11-15 yrs'
            WHEN experience_years <= 20 THEN '4. 16-20 yrs'
            ELSE '5. 21+ yrs' END                AS experience,
       COUNT(*)                                  AS agents,
       ROUND(AVG(deals_closed_lifetime), 1)      AS avg_deals_closed,
       ROUND(AVG(sales), 1)                      AS avg_sales_in_dataset
FROM v_agent_performance
GROUP BY experience
ORDER BY experience;

-- name: Q23 | Agent Performance | Do agents with higher ratings close deals faster?
-- insight: No: the 4.5-5.0 rated agents take about as long (51.7 days) as the 4.0-4.4 band (48.4); the slowest band is 3.5-3.9 (67.7).
-- chart: bar x=rating_band y=avg_closing_days
SELECT CASE WHEN rating < 3.5 THEN '1. Below 3.5'
            WHEN rating < 4.0 THEN '2. 3.5-3.9'
            WHEN rating < 4.5 THEN '3. 4.0-4.4'
            ELSE '4. 4.5-5.0' END                AS rating_band,
       COUNT(*)                                  AS agents,
       ROUND(AVG(avg_closing_days), 1)           AS avg_closing_days,
       ROUND(AVG(avg_days_on_market), 1)         AS avg_days_on_market_in_dataset
FROM v_agent_performance
GROUP BY rating_band
ORDER BY rating_band;

-- name: Q24 | Agent Performance | What is the average commission earned by each agent?
-- insight: Average commission per sale ranges up to $34.0k (A0009, at a 2.85% rate). Total commission is driven mostly by sales volume.
-- chart: bar x=agent_id y=avg_commission_per_sale
SELECT a.agent_id, a.name, a.commission_rate,
       COUNT(s.sale_id)                                              AS sales_closed,
       ROUND(AVG(s.sale_price * a.commission_rate / 100.0), 2)      AS avg_commission_per_sale,
       ROUND(SUM(s.sale_price * a.commission_rate / 100.0), 2)      AS total_commission
FROM agents a
JOIN listings l ON l.agent_id   = a.agent_id
JOIN sales s    ON s.listing_id = l.listing_id
GROUP BY a.agent_id
ORDER BY avg_commission_per_sale DESC;

-- name: Q25 | Agent Performance | Which agents currently have the most active listings?
-- insight: Agent A0023 has the most active listings (446); the top 10 are all within 446-425.
-- chart: bar x=active_listings y=name orientation=h
SELECT a.agent_id, a.name,
       COUNT(*) AS active_listings
FROM agents a
JOIN v_active_listings al ON al.agent_id = a.agent_id
GROUP BY a.agent_id
ORDER BY active_listings DESC, a.agent_id
LIMIT 10;

-- ================================================================ Buyer & Financing Behavior
-- name: Q26 | Buyer & Financing | What percentage of buyers are investors vs end users?
-- insight: Buyers split evenly: 50.1% end users and 49.9% investors.
-- chart: pie names=buyer_type values=buyers
SELECT buyer_type,
       COUNT(*)                                                     AS buyers,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM buyers), 2)   AS pct_of_buyers
FROM buyers
GROUP BY buyer_type
ORDER BY buyers DESC;

-- name: Q27 | Buyer & Financing | Which cities have the highest loan uptake rate?
-- insight: Loan uptake is about 50% everywhere, from 49.5% (Phoenix) to 51.0% (Los Angeles).
-- chart: bar x=city y=loan_uptake_pct
SELECT l.city,
       COUNT(*)                            AS buyers,
       SUM(b.loan_taken)                   AS buyers_with_loan,
       ROUND(AVG(b.loan_taken) * 100, 2)   AS loan_uptake_pct
FROM buyers b
JOIN sales s    ON s.sale_id    = b.sale_id
JOIN listings l ON l.listing_id = s.listing_id
GROUP BY l.city
ORDER BY loan_uptake_pct DESC;

-- name: Q28 | Buyer & Financing | What is the average loan amount by buyer type?
-- insight: Investors and end users borrow almost the same on average (about $5.21M).
-- chart: bar x=buyer_type y=avg_loan_amount
SELECT buyer_type,
       COUNT(*)                      AS loans,
       ROUND(AVG(loan_amount), 2)    AS avg_loan_amount
FROM buyers
WHERE loan_taken = 1
GROUP BY buyer_type
ORDER BY avg_loan_amount DESC;

-- name: Q29 | Buyer & Financing | Which payment mode is most commonly used?
-- insight: Cash is used most (25.4%), but all four payment modes are within 0.7 points of each other.
-- chart: bar x=payment_mode y=buyers
SELECT payment_mode,
       COUNT(*)                                                     AS buyers,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM buyers), 2)   AS pct_of_buyers
FROM buyers
GROUP BY payment_mode
ORDER BY buyers DESC;

-- name: Q30 | Buyer & Financing | Do loan-backed purchases take longer to close?
-- insight: Loan-backed purchases took about one day longer (62.2 vs 61.1 days on market): a negligible difference.
-- chart: bar x=financing y=avg_days_on_market
SELECT CASE b.loan_taken WHEN 1 THEN 'Loan-backed' ELSE 'No loan' END AS financing,
       COUNT(*)                            AS buyers,
       ROUND(AVG(s.days_on_market), 2)     AS avg_days_on_market
FROM buyers b
JOIN sales s ON s.sale_id = b.sale_id
GROUP BY b.loan_taken
ORDER BY avg_days_on_market DESC;
