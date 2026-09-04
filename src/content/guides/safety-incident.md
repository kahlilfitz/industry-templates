# Safety Incident Assist

For the EHS lead or supervisor who needs every incident handled the same way, whether it
arrives as a form, an email, or a voice note at the end of a night shift.

It takes the report, classifies severity, near-miss status and OSHA recordability *and*
reportability, routes it to the right investigator with the regulatory clocks attached, and
drafts the incident summary and root-cause template.

## How it works

| # | Skill | Job |
|---|-------|-----|
| 1 | `incident-intake` | Receives the report from a form, email or voice note into the contract |
| 2 | `ehs-knowledge-retrieve` | Pulls the applicable policy, JHA and recordability guidance |
| 3 | `severity-recordability` | Classifies severity, near-miss and OSHA recordability/reportability (deterministic) |
| 4 | `routing-notify` | Routes to the right investigator and builds the notification list with regulatory clocks (deterministic) |
| 5 | `incident-writeup` | Drafts the incident summary and RCA template |

## The case that shows why it exists

A hand was caught in stamping press M-14 on night shift. The night-shift lead left a voice note
that downplays it: *looked minor, bit of a cut, we bandaged it up and sent him home — can we
just log it as first aid?* Taken at face value, that is a first-aid, non-recordable case.

Two documents change the answer:

- **The day-shift correction and first-responder note:** the worker was admitted to hospital
  overnight, had surgery on two fingers, and is at least five days away from work. That is
  recordable, and the clock has already started.
- **History:** this is the third hand incident on M-14 this year — two near-misses and a prior
  first-aid finger injury. A pattern, not an accident.

The downgrade is the most expensive mistake available here, and it is the easiest one to make.

## What you bring

The incident report in whatever form it arrived, witness statements, the prior-incident log, and
your EHS policy and JHA excerpts.

## Boundaries

Draft-first. The template does **not** file OSHA reports and does **not** send notifications — a
human signs off on both. It keeps the reporting checklist and audit trail intact so that sign-off
is quick.

Grounded in OSHA 300/300A, ISO 45001, JHA/HIRA and internal EHS policy — see `references/`.

## Skills in this package

- **ehs-knowledge-retrieve** — Retrieves the OSHA recordability criteria, ISO 45001 clauses, JHA/HIRA and internal EHS policy relevant to an incident and attaches them plus prior similar incidents to the mfg.safety-incident-assist.v1 contract. Use when the user says "pull the OSHA criteria", "get the JHA for this task", "have we had this incident before", "what does policy say", or after incident-intake completes.
- **incident-intake** — Receives a safety-incident report from a form, email or voice note and pulls it into the mfg.safety-incident-assist.v1 contract inputs. Use when the user says "log this incident", "new incident report", "someone got hurt", "intake this near miss", "process this safety report", or when a Safety Incident Agent run begins.
- **incident-writeup** — Drafts the incident summary and the root-cause-analysis (RCA) template from the assembled contract payload, with every determination cited to OSHA, ISO 45001, the JHA and internal policy. Use when the user says "draft the incident summary", "write up the incident", "give me the RCA template", "prepare the OSHA writeup", or after routing-notify completes.
- **routing-notify** — Routes a classified incident to the right investigator, builds the owner-notification list, and starts any OSHA regulatory clock, deterministically. Use when the user says "who investigates this", "who do we notify", "route this incident", "start the OSHA clock", "who owns this", or after severity-recordability completes.
- **severity-recordability** — Classifies a safety incident's severity, near-miss status, OSHA recordability (with the OSHA 300 column) and reportability (with the 1904.39 clock), deterministically. Use when the user says "is this recordable", "classify this incident", "is this an OSHA reportable", "what severity is this", "do we have to report this", or after ehs-knowledge-retrieve completes.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/safety-incident/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/safety-incident/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
