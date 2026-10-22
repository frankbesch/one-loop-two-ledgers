# Step 6 quotas

## Money errors: per month, every month (so 16 or more per class in the scored months 3-6)

| Class (`money_error`) | Per month | Definition |
|---|---|---|
| `wrong_decimal` | 4 | Printed owner decimal differs from the division order in force on the service date |
| `wrong_rate` | 4 | Rate-billed line whose unit rate differs from the contract rate in force for that vendor and service on the service date |
| `nonconsent_property` | 4 | Line billed on a property where the owner elected non-consent before the service date |
| `afe_overrun` | 4 | Line whose cumulative gross billed to its AFE, in billing order across all months, passes the approved amount times (1 + the JOA tolerance) |
| `duplicate` | 4 | Same vendor invoice number and same gross as a line already billed in this or an earlier month (the later line carries the label) |
| `date_window` | 4 | Service date after the billing month's end, or more than 24 months before it |

At most one money error per line. `money_error` is `none` on every other line. Every money-error line also carries `error_dollars`: the owner's net overcharge in dollars (the full net for `nonconsent_property` and `duplicate`).

## Approval claims (job B labels): per month

| Case | Per month |
|---|---|
| supported (exact, reformatted, or reworded) | 6 |
| unsupported placeholder (at least half paraphrased) | 3 |
| unsupported unknown number | 3 |
| unsupported no number | 2 |
| unsupported wrong property | 2 |
| contradicted (declined AFE) | 2 |
| other_authority | 2 |
| no_claim bait | 2 |
| hard (claim only in a remark) | 2, drawn from the cases above |
| remarks that name a line and claim nothing | 2 |

## Linking

| Case | Per month |
|---|---|
| property printed as a name variant (not the exact property number or name) | 8 |

## Reference changes (each takes effect on a stated date)

- A share transfer in month 2: the owner's decimal on one property changes.
- A new AFE approved in month 3.
- A non-consent election on one property in month 5. The `nonconsent_property` lines from month 5 on follow it; months 1-4 use earlier elections set up in month 1.
- One contract rate change in month 4.
