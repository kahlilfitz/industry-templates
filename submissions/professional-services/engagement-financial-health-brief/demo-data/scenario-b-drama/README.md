# Scenario B - drama path

Clearwater Methods' operating model engagement looks healthy if the reviewer reads only the
headline finance export. Realisation is above threshold, burn is within plan tolerance and current
margin is still on plan. A naive review would leave the status green.

The fixed definitions expose the problem:

1. `WIP-B-004` and `WIP-B-005` put $50,000 into the 90+ day WIP bucket. The configured reserve
   turns that into a $31,000 collectability risk across all ageing buckets.
2. The actual staffing mix is junior-heavy. Partner and director review hours assumed by the plan
   have not been booked, adding $15,640 of deferred senior review cost to ETC.
3. Three of nine due milestones have slipped, adding $13,650 of remediation cost.
4. The system ETC is still equal to the original remaining plan, so the engine adds the missing
   work rather than accepting the stale forecast.
5. The practice benchmark file uses `ps-utilisation-gross-capacity-v1`, not the engagement's
   `ps-commercial-control-standard-v1`, so benchmark comparison is refused.

Expected: `health_calc` downgrades the engagement despite green-looking headline metrics and
refuses benchmark comparison. `driver_attribute` decomposes the $31,290 EAC cost variance as
$2,000 actual burn variance + $0 system remaining variance + $13,650 milestone slip remediation +
$15,640 deferred senior review, reconciling exactly to the total.
