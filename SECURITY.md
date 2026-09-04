# Security

## Reporting a vulnerability

If you believe you have found a security issue in this repository — for example, a template
that could cause an agent to exfiltrate data, or a script with an injection flaw — please
report it privately rather than opening a public issue.

Use GitHub's [private vulnerability reporting](https://github.com/SravaniSeethi/industry-templates/security/advisories/new)
on this repository.

Please include the template slug, the file, and a description of the impact. You should get an
acknowledgement within a few days.

## What to expect from these templates

Every template here is community-provided example content. Before installing one:

- **Read the package.** It runs with your agent's permissions. The skills, scripts and reference
  rules are all plain text in `submissions/<slug>/`.
- **The scripts are deterministic engines.** They read the contract JSON and write JSON. They do
  not make network calls.
- **The demo data is synthetic.** Nothing in `demo-data/` is real customer, supplier or personal
  data.
- **Nothing writes back.** Templates are draft-first by design: no system-of-record writes, no
  auto-send, no auto-file.

Replace the reference rules and thresholds with your own controlled documents before using any
template on real work.
