# Notice

## Site design and submission architecture

The gallery's design language and its `submissions/` → generated-page architecture are adapted
from [`microsoft/cat-agent-skills`](https://github.com/microsoft/cat-agent-skills), used under
the MIT License:

```
MIT License

Copyright (c) Microsoft Corporation.
```

What is adapted: the Astro + Tailwind site structure, the theme token system, the card and
cover components, the gallery filter island, and the "contributors only touch `submissions/`,
CI generates the rest" build model. What is new here: the industry facet that organises the
gallery, the plugin-package submission format, the importer, and all template content.

## Logo

`public/paw.png` and `public/favicon.png` are the paw mark from that same repository
(`public/paw.png`), reused under its MIT License and resized. The MIT License grants the right
to use and modify the file; it does not grant trademark rights, so if this gallery ever needs a
mark that is unambiguously its own, replace these two files — nothing else references the
artwork.

## Template content

The manufacturing templates in `submissions/` ship **synthetic demo data only**. Part numbers,
suppliers, incidents, measurements and personnel in `demo-data/` are invented for
demonstration. The excerpts in each package's `references/` are illustrative summaries of
public standards (ISO 9001, IATF 16949, ISO 45001, OSHA 300/300A, ASME Y14.5, ISO 55000,
ISO 19011) — they are **not** the standards themselves, which remain the copyright of their
publishers. Buy the standard, and replace the reference excerpts with your own controlled
documents before using any of this on real work.
