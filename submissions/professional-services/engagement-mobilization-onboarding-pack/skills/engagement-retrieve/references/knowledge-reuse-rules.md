# Knowledge Reuse Rules
## 1. Closeout adapter
### 1.1 Contract version required
Closeout input must declare `ps.engagement-closeout-knowledge-harvest.v1`.
### 1.2 Knowledge record required
Top-level `knowledge_record` (an object) and `released_assets`, and `knowledge_record.reusable_assets` and `knowledge_record.lessons`, are required lists of objects. An absent member is not an empty list: a missing or null member stops the run with an input error and nothing is written. An explicitly empty list is valid. The closed engagement block (`engagement`) may be absent or null; its records are then unattributed (confidentiality-and-ethical-wall-rules.md #3.3).
### 1.3 Allowed fields only
The adapter reads only `knowledge_record`, `released_assets` and provenance/citations; never `held_assets` or `candidate_assets`.
### 1.4 Types validated, fail closed
Every field the engine reads is type-checked: IDs, titles, descriptions and citations are strings; `tags` and `evidence_citations` are arrays of strings; `knowledge_record.record_id` is a string or null and `evidence_ids` on an asset or lesson is an array (or null) whose items are identifier strings (null or blank items are absent); `review_required`, `rewrite_required` and `review_candidate` are true/false; `confidence` is a number from 0 to 1. A wrong JSON type stops the run with an input error rather than being coerced. Every Closeout identifier (`asset_id`, `cluster_id`, `record_id`, `evidence_ids`, and `engagement_id` and `matter_id` at the record and engagement levels) must have the identifier shape and be a JSON string (confidentiality-and-ethical-wall-rules.md #1.3); prose, spaces or punctuation in one, or a number, true/false, object or array in its place, stops the run with an input error that names the path and does not repeat the value. Flagged Closeout text is withheld (confidentiality-and-ethical-wall-rules.md #4.3). An asset or lesson with a blank or withheld ID joins nothing and is excluded (`not_in_released_assets`, `no_lesson_id`). A missing title, description, category or guidance gets an engine default, never null, so every emitted knowledge item is complete (confidentiality-and-ethical-wall-rules.md #1.3).
## 2. Clearance
### 2.1 Released asset required
A reusable asset must also appear in `released_assets` with a release-candidate clearance state.
### 2.2 Confidentiality permission required
Closeout's `released_assets` release-candidate state is the permission for internal engagement reuse. An explicit `confidentiality_permission` other than `cleared_for_internal_engagement_reuse` excludes the item.
### 2.3 Draft not publish
Release candidates remain draft knowledge for practice review. Only an explicit `review_required: false` clears review; true, absent or null items are labelled `pending_practice_review`: reference the title and citation only until Knowledge Management confirms.
### 2.4 Lessons need a governed rewrite state
A lesson is matched only when `rewrite_required` is explicitly false; its drafting guidance is used, never source text.
## 3. Matching
### 3.1 Relevance is deterministic
Relevance is computed from token overlap between the engagement scope and an item's narrative only (title, description, tags and category). IDs, citations, scores, confidence and other metadata never contribute terms or numbers, so an asset ID built from this engagement's words does not make it relevant.
### 3.2 Sources travel with digest
Every item carries source, confidence, provenance and citations.
