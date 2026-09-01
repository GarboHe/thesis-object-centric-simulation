# CSQ3 OCPQ Query Definitions

This file documents the OCPQ queries preserved for reproducing CSQ3 in the thesis. The machine-readable query definitions are stored separately as OCPQ JSON files; this document provides a human-readable specification and the expected result checkpoints.

## 1. CSQ3 research question

**CSQ3 – Synchronisation and post-readiness accounting delay**

> How much simulated synchronisation delay occurs between invoice receipt and asset readiness, and how much additional time elapses from asset readiness to accounting-voucher posting?

The analysis intentionally retains `Invoice` and `Asset` as separate object types and relates them through downstream accounting events.

## 2. Software and source data

The query definitions were prepared in **OCPQ v0.11.2**.

Use the preserved baseline OCEL for the thesis (`Run 1`) as the OCPQ input. The query JSON files are graphical-query definitions: copy the complete JSON text, create/select an empty query canvas in OCPQ, paste the JSON into the canvas, and evaluate the restored query.

For each query, preserve both:

- the JSON query definition; and
- the raw OCPQ Situation Table exported after evaluation.

Do not manually edit the raw Situation Table before running the Python analysis.

---

## 3. Main Invoice–Asset query

**Machine-readable file:** `csq3_invoice_asset_query.json`

**Thesis role:** source query for **Figure 4.4** and source of the 25-row Situation Table used for **Table 4.12** and **Figure 4.5**.

### Object variables

- `o1: Invoice`
- `o2: Asset`

### Event variables

- `e1: Receive Invoice`
- `e2: Put Asset Into Use`
- `e3: Verify Accounting Prerequisites`
- `e4: Post Accounting Voucher`

### Event-to-object filters

The preserved query requires:

- `e1` related to `o1` (`Invoice`);
- `e2` related to `o2` (`Asset`);
- `e3` related to both `o1` and `o2`;
- `e4` related to both `o1` and `o2`.

This binds invoice receipt, asset readiness, prerequisite verification, and voucher posting within the same related Invoice–Asset constellation.

### Temporal constraint

```text
e1.time() <= e3.time()
&& e2.time() <= e3.time()
&& e3.time() <= e4.time()
```

### Labels in the preserved query

```text
accounting_ready_time = max(e1.time(), e2.time())
synchronization_delay = max(e1.time(), e2.time()) - min(e1.time(), e2.time())
invoice_wait          = max(e1.time(), e2.time()) - e1.time()
asset_wait            = max(e1.time(), e2.time()) - e2.time()
readiness_to_verify   = e3.time() - max(e1.time(), e2.time())
readiness_to_post     = e4.time() - max(e1.time(), e2.time())
invoice_last          = e1.time() > e2.time()
asset_last            = e2.time() > e1.time()
tie                   = e1.time() == e2.time()
```

The thesis definitions are therefore implemented directly in the OCPQ query:

```text
t_ready = max(t_invoice, t_asset)
d_sync = abs(t_invoice - t_asset)
ready_to_verify = t_verify - t_ready
ready_to_post = t_post - t_ready
```

`d_sync` is reported in calendar days. The downstream durations are reported in minutes. The definition of `t_ready` is an analytical definition for the two explicitly timestamped prerequisite paths represented in this query; it does not claim that these two events exhaust all documentary conditions in the real organisation.

### Expected query output

```text
25 satisfied bindings
```

One row represents one posted Invoice–Asset analytical binding.

---

## 4. Voucher-rework query

**Machine-readable file:** `csq3_voucher_rework_query.json`

This query provides the cross-check for the three 79-minute observations.

### Object variable

- `o1: Voucher`

### Event variables

- `e1: Modify Accounting Voucher`
- `e2: Post Accounting Voucher`

### Event-to-object filters

- `e1` related to `o1`;
- `e2` related to `o1`.

### Temporal constraint

```text
e1.time() <= e2.time()
```

### Expected query output

```text
3 satisfied bindings
```

Expected vouchers:

```text
V-O-14
V-O-21
V-O-22
```

The `e2` value in this Situation Table is the `Post Accounting Voucher` event ID. Join it to `e4` in the main Invoice–Asset Situation Table. The three matched rows must be exactly the three `readiness_to_post = 79 minutes` observations. All remaining 22 main-query rows must have `readiness_to_post = 29 minutes`.

---

## 5. Expected thesis checkpoints

The current thesis reports the following values in Table 4.12:

| Measure | Expected baseline result |
|---|---|
| Prerequisite ordering | Asset readiness later than invoice receipt in 25/25 bindings; no invoice-later cases and no ties |
| Synchronisation delay | Mean 9.14 calendar days; median 7.00; Q1 7.00; Q3 7.73; range 7.00–28.25 |
| Readiness to Verify Accounting Prerequisites | 2 minutes in 25/25 bindings |
| Readiness to Post Accounting Voucher | Mean 35 minutes; median 29; range 29–79 minutes |
| Normal post-readiness path | 22/25 Requirements posted after 29 minutes |
| Voucher-rework path | 3/25 Requirements posted after 79 minutes |

The three 79-minute observations must coincide exactly with `V-O-14`, `V-O-21`, and `V-O-22` from the voucher-rework query.

---

## 6. Minimum CSQ3 evidence chain

The minimum CSQ3 reproduction chain is:

```text
Run 1 OCEL
→ csq3_invoice_asset_query.json
→ raw 25-row Invoice–Asset Situation Table
→ csq3_descriptive_analysis.py
→ Table 4.12 + Figure 4.5 + numerical/intermediate outputs
```

with the following independent cross-check:

```text
Run 1 OCEL
→ csq3_voucher_rework_query.json
→ raw 3-row voucher-rework Situation Table
→ join by Post Accounting Voucher event ID
→ exactly the three 79-minute rows
```

A separate Requirement–Voucher mapping query is **not required to reproduce CSQ3**. It can be retained elsewhere as supporting cross-question traceability, especially for CSQ2, but it is not part of the minimum CSQ3 computation.
