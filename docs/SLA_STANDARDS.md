# SLA Turnaround-Time Standards

TAT-PAS measures pharmacy turnaround time (TAT) as the elapsed time from when a
prescription is submitted to when it is dispensed, and flags an SLA breach when
that time exceeds the threshold for the order's priority. A warning fires at 75%
of the threshold.

The default thresholds are grounded in published medication-administration
standards rather than chosen arbitrarily, so the audit trail and TAT/PAS reports
are defensible.

## Default thresholds (minutes)

| Priority   | Threshold | Basis |
|------------|-----------|-------|
| STAT       | 15        | ~15 min pharmacy dispense; 30 min order-to-administration (ISMP). |
| Urgent     | 30        | Urgent / NOW orders within ~30 min (ISMP / ASHP). |
| Routine    | 60        | Standard scheduled window of ~60 min (ISMP, consensus of 9 studies). |
| Discharge  | 45        | Prepared within the discharge workflow. |
| NICU       | 20        | Tightened from STAT/urgent for neonatal risk. |
| Chemo      | 120       | Extended to allow safe preparation and verification. |

These values are seeded into the `sla_config` collection and can be changed on
the SLA Configuration page by the auditor (compliance owner) or admin (system
configuration). Every change is recorded in the audit trail.

## How the standards map to TAT-PAS stages

TAT-PAS records per-stage times across the prescription lifecycle
(ordered -> submitted -> verified -> dispensed -> administered). The SLA
threshold above applies to the pharmacy turnaround segment (submitted ->
dispensed), which is the segment the cited standards measure.

## Sources

- ISMP Acute Care Guidelines for Timely Administration of Scheduled Medications.
  https://www.ismp.org/sites/default/files/attachments/2018-02/tasm.pdf
- ASHP / SICP Medication Use Benchmarking Toolkit.
  https://www.ashp.org/-/media/assets/pharmacy-practice/resource-centers/practice-management/ASHP-SICP-Medication-Use-Benchmarking-Toolkit.pdf
- AHRQ, Medication Turnaround Time in the Inpatient Setting (quick reference guide).
  https://digital.ahrq.gov/sites/default/files/docs/page/medication-turnaround-time-quick-reference-guide.pdf
