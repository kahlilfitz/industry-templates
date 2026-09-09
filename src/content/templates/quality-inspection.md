---
name: Quality Inspection & Nonconformance
description: "Clear an inspection lot end to end: read the part spec, drawing, inspection plan, CoC and measurement export, compare every actual against tolerance, grade each defect by severity and disposition, and draft the nonconformance report with every call cited back to the spec."
agentDescription: "Manufacturing Wave 1 Cowork plugin: clear an inspection lot. Reads part specs, drawings, inspection plans, CoC and measurement exports; compares actual measurements against tolerances (deterministic tolerance_check, with CoC-vs-measurement cross-check); grades each defect by severity and disposition (deterministic defect_grade rules engine); drafts the nonconformance report with every call cited to the spec. Draft-first; document-grounded. Ends at NCR creation and hands off to Quality Incident & CAPA (Wave 2)."
industry: Manufacturing
platforms: [Cowork]
type: plugin
tags: [quality, inspection, ncr, nonconformance, tolerance, mrb]
author: Industry Templates
authorUrl: "https://github.com/SravaniSeethi"
authorGithub: SravaniSeethi
version: 2.0.0
createdAt: 2026-08-01
updatedAt: 2026-09-04
bundle: bundles/quality-inspection.zip
skills:
  - name: defect-grade
  - name: ncr-draft
  - name: spec-ingest
  - name: tolerance-check
featured: true
---
Clear an inspection lot end to end: read the part spec, drawing, inspection plan, CoC and measurement export, compare every actual against tolerance, grade each defect by severity and disposition, and draft the nonconformance report with every call cited back to the spec.

> **Manufacturing template.** This is a Microsoft 365 Copilot **Cowork** plugin package — a `.zip` bundling the skills, rules, and contracts below.

## Skills in this package

- **defect-grade** — Grades each out-of-tolerance characteristic by severity and recommends a disposition (use-as-is / rework / scrap / return-to-vendor / hold-for-review) using the deterministic disposition rules engine. Use when the user says "grade the defects", "what disposition?", "how bad is it?", "can we ship it?", or after tolerance-check finds any out-of-tolerance characteristic.
- **ncr-draft** — Drafts the nonconformance report (NCR) and inspection summary from the graded contract payload, with every determination cited to the spec and rules. Use when the user says "draft the NCR", "write up the nonconformance", "inspection summary please", or after defect-grade completes with defects.
- **spec-ingest** — Reads part specs, drawings, inspection plans, certificates of conformance and measurement exports for an inspection lot, and normalizes them into the mfg.quality-inspection.v1 contract inputs. Use when the user says "clear this inspection lot", "load the inspection results", "read the spec for part <PN>", "review lot <LOT-ID>", or when an inspection lot review begins.
- **tolerance-check** — Compares actual measurements against spec tolerances for an inspection lot, computes per-characteristic statistics, flags out-of-tolerance and marginal characteristics, and cross-checks certificate claims against measured reality - deterministically. Use when the user says "check tolerances", "compare against spec", "any out-of-spec?", or after spec-ingest completes in a lot review.

## Demo data

The package ships synthetic demo scenarios so you can run the template end-to-end before wiring it to your own systems. Each scenario has a happy path and a messier one, with the expected outputs alongside the inputs.

## Install

1. Download the plugin package (the `.zip` on this page).
2. Upload it to your tenant via **M365 admin center › Manage apps › Upload custom app**, or sideload it for testing with the [Microsoft 365 Agents Toolkit CLI](https://learn.microsoft.com/en-us/microsoftteams/platform/toolkit/microsoft-365-agents-toolkit-cli) (`atk install --file-path <zip> --scope Personal`).
3. Open **Cowork › Sources & Skills › Plugins** and enable it from the **Discover** section.

See [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) for details.

## Test evidence

A test report and sample prompt set are kept with the source, in [`submissions/manufacturing/quality-inspection/tests/`](https://github.com/SravaniSeethi/industry-templates/tree/main/submissions/manufacturing/quality-inspection/tests).

## Before you use it on real work

This template is draft-first and document-grounded: it prepares the work for a person to review and sign off, and it does not write back to a system of record. The rules, thresholds, and reference documents in `references/` are examples — replace them with your own before production use.
