# Centrifugal Pump Troubleshooting Guide (field quick-reference)

Grounded in OEM Pump Manual CP-200 and site reliability standards (RCM, ISO 55000).

## Symptom -> first checks

| Symptom / alarm | Look at | Likely modes (manual) |
|---|---|---|
| High vibration (VIB-HH) | Bearings, coupling alignment | Bearing degradation §6.3, misalignment §5.2 |
| High bearing temp (TEMP-BRG-H) | Lubrication, bearing wear | Bearing degradation §6.3 |
| Grinding / rumble | Bearings, impeller | Bearing §6.3, cavitation §6.4 |
| Overload trip (OL-TRIP) | Motor current, **history of resets** | Electrical §7.1 *only if no mechanical signs* |
| Seal leak (SEAL-LEAK) | Gland, shaft sleeve | Seal failure §6.1 |
| Low flow (FLOW-LO) / low suction (SUCT-LO) | Suction, NPSH | Cavitation §6.4 |

## Golden rule (reliability)
A cheap symptomatic fix that keeps coming back is a signal, not a solution. If an overload
reset has been done repeatedly on the same asset and vibration or bearing temperature is
climbing, stop resetting and investigate the bearing/coupling per §6.3 / §5.2. Open a
root-cause analysis (RCM) — see rcm-iso55000-excerpts.md.
