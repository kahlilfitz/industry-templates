# Scenario B - escalation path
"Just key it, truck at 2." Four traps in one line:
1. Alias CHOCV resolves to TWO products (vegan + standard) -> AMBIGUOUS_SKU (#1.1).
2. 500 EA from a customer that always orders CS24, typical qty 40 -> UOM + QTY anomalies (#2.1).
3. 54.90 vs list 62.40 = 12% below with no promo reference -> PRICE_DEVIATION (#3.1).
4. Exposure would pass the credit limit -> CREDIT_REVIEW queued, customer not bounced (#4.1).
Expected: 4+ exceptions routed with recommended corrections; ONE clarification draft
asking product/UOM/price; order held at L2, never keyed. A naive clerk rekeys as-is and
ships 500 eaches of the wrong bar below cost.
