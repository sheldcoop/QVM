# QVM Dashboard - open questions

## Q1: Lab time zone
`js/config.js` defaults to Europe/Vienna (tracker's zone). Confirm the QVM lab's zone.

## Q2: Tolerance editing — RESOLVED (M5, see D8)
Analyst-editable Settings view, no PIN, persisted to localStorage.

## Q3: Sample data bundle
Which `.txt` logs ship as built-in samples? Proposal: the two Core Shrinkage
CAM-order files plus one PtV/VtP pair from `qvm_dashboard/sample_data/` (M9).

## Q4: Theme subset
Keep all tracker themes or ship fewer? Proposal: keep all — zero maintenance cost.
