-- Bulk-sale-tax candidate-pair finder for trade run verification.
--
-- Top sensitive (Metals/Minerals) one-hop pairs ranked by unit profit.
-- For each commodity in those categories, picks the globally cheapest
-- supplier and the globally dearest demander, then joins to station and
-- system names. safe_cap = floor(demand / 4) is the planned quantity the
-- 25% bulk-sale cap should produce. Demand >= 100 keeps the cap clearly
-- visible against a normal cargo bay.
--
-- Fleet carriers (Drake-Class, Station.type_id = 5) are excluded on both
-- sides because their prices are owner-set rather than from the background
-- simulation; the unanchored search regularly surfaces carrier-to-carrier
-- outliers that are noise for cap verification.
--
-- Run: sqlite3 <db> < bulk_sale_tax_candidates.sql
--
-- Pick a row where safe_cap < your test capacity, then:
--   trade run --from "<source>" --to "<destination>" \
--     --capacity 256 --credits 1000000000 \
--     --hops 1 --jumps-per 8 --ly-per 40
-- Expected cargo quantity == safe_cap.

-- Pre-check: confirm the EDCD category names exist verbatim.
-- Two rows expected. Zero means the planner helper resolves to no
-- sensitive items and the cap silently won't fire.
SELECT category_id, name
FROM Category
WHERE name IN ('Metals', 'Minerals');


-- Top sensitive trades, source and destination stations resolved.
-- Fleet carriers excluded on both sides.
WITH sensitive_items AS (
    SELECT i.item_id, i.name AS commodity
    FROM Item i
    JOIN Category c ON c.category_id = i.category_id
    WHERE c.name IN ('Metals', 'Minerals')
),
best_supply AS (
    SELECT
        si.item_id,
        si.station_id,
        si.supply_price,
        si.supply_units,
        ROW_NUMBER() OVER (
            PARTITION BY si.item_id
            ORDER BY si.supply_price ASC, si.station_id ASC
        ) AS rn
    FROM StationItem si
    JOIN Station st ON st.station_id = si.station_id
    WHERE si.item_id IN (SELECT item_id FROM sensitive_items)
      AND si.supply_price > 0
      AND si.supply_units > 0
      AND st.type_id != 5      -- exclude Drake-Class fleet carriers
),
best_demand AS (
    SELECT
        si.item_id,
        si.station_id,
        si.demand_price,
        si.demand_units,
        ROW_NUMBER() OVER (
            PARTITION BY si.item_id
            ORDER BY si.demand_price DESC, si.station_id ASC
        ) AS rn
    FROM StationItem si
    JOIN Station st ON st.station_id = si.station_id
    WHERE si.item_id IN (SELECT item_id FROM sensitive_items)
      AND si.demand_price > 0
      AND si.demand_units >= 100
      AND st.type_id != 5      -- exclude Drake-Class fleet carriers
)
SELECT
    s.commodity,
    (d.demand_price - bs.supply_price) AS unit_profit,
    d.demand_units                     AS demand,
    (d.demand_units / 4)               AS safe_cap,
    src_sys.name || '/' || src_st.name AS source,
    bs.supply_units                    AS supply,
    bs.supply_price                    AS buy,
    dst_sys.name || '/' || dst_st.name AS destination,
    d.demand_price                     AS sell
FROM sensitive_items s
JOIN best_supply bs ON bs.item_id = s.item_id AND bs.rn = 1
JOIN best_demand d  ON d.item_id  = s.item_id AND d.rn  = 1
JOIN Station src_st ON src_st.station_id = bs.station_id
JOIN System  src_sys ON src_sys.system_id = src_st.system_id
JOIN Station dst_st ON dst_st.station_id = d.station_id
JOIN System  dst_sys ON dst_sys.system_id = dst_st.system_id
WHERE d.demand_price > bs.supply_price
ORDER BY unit_profit DESC
LIMIT 20;
