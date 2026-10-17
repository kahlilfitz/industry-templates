# Credential Taxonomy — Credential & Case Study Assembly

Illustrative taxonomy used by `credential_draft.py` to classify closeout records. Replace with the firm's controlled credential taxonomy.

## 1. Sector
| Value | Match hints |
|---|---|
| `financial-services` | banking, insurance, asset management, payments, wealth |
| `public-sector` | government, agency, municipality, public service |
| `healthcare` | provider, payer, hospital, clinical operations |
| `industrial` | manufacturing, energy, logistics, field operations |
| `technology-media-telecom` | software, platform, media, telecom |
| `cross-industry` | horizontal corporate function or sector not otherwise classified |

## 2. Service line
| Value | Match hints |
|---|---|
| `strategy-advisory` | strategy, operating model, roadmap, business case |
| `technology-transformation` | platform, migration, implementation, integration |
| `data-ai-analytics` | data platform, analytics, AI, automation, insights |
| `risk-regulatory` | compliance, controls, audit, regulatory response |
| `managed-services` | run, operate, managed service, support |

## 3. Capability
| Value | Match hints |
|---|---|
| `process-redesign` | process, workflow, standardisation, operating model |
| `platform-migration` | migration, core platform, legacy replacement |
| `ai-automation` | automation, AI, copilots, intelligent workflow |
| `data-modernisation` | lakehouse, warehouse, data foundation, reporting |
| `change-enablement` | adoption, training, communications, stakeholder enablement |

## 4. Engagement size band
| Band | Rule |
|---|---|
| 4.1 `small` | fees under 250000 or duration under 8 weeks |
| 4.2 `medium` | fees from 250000 to 999999 or duration from 8 to 25 weeks |
| 4.3 `large` | fees from 1000000 to 4999999 or duration from 26 to 51 weeks |
| 4.4 `strategic` | fees at least 5000000, duration at least 52 weeks, or board-visible enterprise programme |

## 5. Outcome type
| Value | Match hints |
|---|---|
| `cost-reduction` | cost, spend, savings, productivity |
| `cycle-time` | time, speed, throughput, processing time |
| `risk-reduction` | risk, control, compliance, audit finding |
| `revenue-growth` | revenue, conversion, sales, retention |
| `experience-improvement` | customer, employee, satisfaction, NPS |
| `resilience-quality` | resilience, quality, defect, reliability |

## 6. Taxonomy match confidence
| Rule | Condition | Effect |
|---|---|---|
| 6.1 | Match confidence is at least 0.72 | Accept taxonomy match |
| 6.2 | Match confidence is below 0.72 | Keep best match but escalate for taxonomy owner review |
| 6.3 | Multiple values tie within 0.05 | Mark as ambiguous and escalate |
