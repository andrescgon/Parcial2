# Harness report - kevin_andres

Automated score: **27.0 / 70.0**

| Req | Title | Status | Points |
|---|---|---|---|
| R1 | Flight search latency | passed | 4.0/4 |
| R2 | No overselling under concurrency | passed | 10.0/10 |
| R3 | Reservation retrieval | passed | 3.0/3 |
| R4 | EMR job produces curated Parquet | not_verified | 0.0/8 |
| R5 | Glue Catalog tables per contract | not_verified | 0.0/6 |
| R6 | Athena correctness and partition pruning | not_verified | 0.0/8 |
| R7 | Analytics endpoint backed by Athena | not_verified | 0.0/8 |
| R8 | Customer flow in browser | passed | 6.0/6 |
| R9 | Manager panel matches endpoint | passed | 4.0/4 |
| R10 | No leftover EMR / bounded EMR hours | not_verified | 0.0/5 |
| R11 | Simple low-cost architecture | not_verified | 0.0/4 |
| R12 | Cost projection | not_verified | 0.0/4 |

## R1 Flight search latency - passed
- passed: `test_search_p95` 
- evidence: 100 requests, concurrency 20: p50=0.047s p95=0.064s

## R2 No overselling under concurrency - passed
- passed: `test_last_seat_exactly_one` 
- passed: `test_k_seats_exactly_k` 
- evidence: round 1: 201=1 409=49 other=0
- evidence: round 2: 201=1 409=49 other=0
- evidence: round 3: 201=1 409=49 other=0
- evidence: round 4: 201=1 409=49 other=0
- evidence: round 5: 201=1 409=49 other=0
- evidence: K=3 round 1: 201=3
- evidence: K=3 round 2: 201=3
- evidence: K=3 round 3: 201=3
- evidence: K=3 round 4: 201=3
- evidence: K=3 round 5: 201=3

## R3 Reservation retrieval - passed
- passed: `test_get_reservation` 
- passed: `test_unknown_reservation_404` 

## R4 EMR job produces curated Parquet - not_verified

## R5 Glue Catalog tables per contract - not_verified

## R6 Athena correctness and partition pruning - not_verified

## R7 Analytics endpoint backed by Athena - not_verified

## R8 Customer flow in browser - passed
- passed: `test_search_reserve_confirm` 
- evidence: UI created reservation 44 for a flight; backend returns it

## R9 Manager panel matches endpoint - passed
- passed: `test_manager_panel_equals_endpoint` 
- evidence: LET-PSO 2024-05: panel=0.8570 endpoint=0.8566 truth=0.8566

## R10 No leftover EMR / bounded EMR hours - not_verified

## R11 Simple low-cost architecture - not_verified

## R12 Cost projection - not_verified
