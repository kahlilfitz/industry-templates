# Notice

## Submission architecture

The `submissions/` package layout and generated catalog-branch approach are adapted from
[`microsoft/cat-agent-skills`](https://github.com/microsoft/cat-agent-skills), used under the
MIT License:

```
MIT License

Copyright (c) Microsoft Corporation.
```

What is adapted: the contributor workflow in which authors edit only `submissions/` and CI
generates distribution artifacts. What is new here: the industry-organized plugin package
format, bundle importer, deterministic engine patterns, demo data and template content.

## Template content

The manufacturing templates in `submissions/` ship **synthetic demo data only**. Part numbers,
suppliers, incidents, measurements and personnel in `demo-data/` are invented for
demonstration. The excerpts in each package's `references/` are illustrative summaries of
public standards (ISO 9001, IATF 16949, ISO 45001, OSHA 300/300A, ASME Y14.5, ISO 55000,
ISO 19011) — they are **not** the standards themselves, which remain the copyright of their
publishers. Buy the standard, and replace the reference excerpts with your own controlled
documents before using any of this on real work.
