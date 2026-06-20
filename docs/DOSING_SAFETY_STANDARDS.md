# Prescription Audit: Dosing Safety Standards

The prescription audit (flagging) engine checks each prescription for clinical
safety when it is created. This is separate from the SLA engine: the SLA checks
**timing** (how fast a prescription is dispensed), while the audit engine checks
**drug content** (dose, allergies, interactions, weight/age appropriateness).

This document covers the weight- and age-based dosing checks, which are grounded
in published dosing guidance rather than arbitrary numbers.

## How dose checks work

For each medication the engine derives the total milligrams per day from the
ordered dose and frequency (e.g. `400 mg TDS` = 1200 mg/day). It then compares
that against the drug's limits:

1. **Weight-based limit (mg/kg/day)** - when the patient's weight is on record,
   the ordered mg/kg/day is compared to the drug's paediatric ceiling. This is
   the primary safeguard for children, where ~87% of medications are dosed by
   weight.
2. **Absolute daily ceiling (mg/day)** - catches overdoses regardless of weight,
   including adults.
3. **Generic fallback** - drugs without a reference entry use a conservative
   flat threshold and a 25 mg/kg/day paediatric caution level.

Neonates (under ~2 months) always warrant pharmacist review because of immature
organ function; any neonatal order is flagged for specialised verification.

## Reference limits (current defaults)

| Drug         | Adult max single | Max mg/kg/day | Absolute max/day |
|--------------|------------------|---------------|------------------|
| Paracetamol  | 1000 mg          | 75 mg/kg      | 4000 mg          |
| Ibuprofen    | 400 mg           | 40 mg/kg      | 1200 mg          |
| Amoxicillin  | 500 mg           | 90 mg/kg      | 3000 mg          |
| Diclofenac   | 50 mg            | 3 mg/kg       | 150 mg           |
| Prednisolone | 60 mg            | 2 mg/kg       | 60 mg            |
| Azithromycin | 500 mg           | 12 mg/kg      | 500 mg           |
| Furosemide   | 80 mg            | 6 mg/kg       | 600 mg           |

These can be extended in `app/services/flagging_service.py` (`_DOSE_LIMITS`).

## Sources

- BNF for Children (paediatric weight-based dosing; max daily doses).
  https://bnfc.nice.org.uk/
- MSF Essential Drugs - Paracetamol (acetaminophen), oral.
  https://medicalguidelines.msf.org/en/viewport/EssDr/english/paracetamol-acetaminophen-oral-16684400.html
- Drugs.com - Acetaminophen dosage (max dose and adjustments).
  https://www.drugs.com/dosage/acetaminophen.html
- ISMP guidance on weight-based paediatric dosing and double-checks for
  high-alert medications.
