# Scenario B - drama path
The pursuit lead asks to "just copy" a prior executed SOW because it was accepted quickly. That
prior SOW silently carries two QRM one-off concessions for a different client: a client-favourable
limitation-of-liability clause and an uncapped data-protection indemnity.

The discovery notes sound confident, but they never establish who supplies test data, what
acceptance means or what plan supports the go-live date.

Expected: `scope_extract.py` blocks acceptance, test-data obligations and the go-live commitment;
`clause_select.py` selects approved clauses but marks acceptance and data protection as
`thin_input_blocked`; `deviation_flag.py` flags the inherited limitation-of-liability and
data-protection language as critical deviations requiring QRM, legal and partner review. A naive
reviewer copies the old SOW; the engine refuses.
