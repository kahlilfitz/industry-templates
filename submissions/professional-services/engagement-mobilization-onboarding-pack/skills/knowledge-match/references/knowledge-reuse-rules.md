# Knowledge Reuse Rules
## 1. Closeout adapter
### 1.1 Contract version required
Closeout input must declare `ps.engagement-closeout-knowledge-harvest.v1`.
### 1.2 Knowledge record required
Top-level `knowledge_record` is required.
### 1.3 Allowed fields only
The adapter reads only `knowledge_record`, `released_assets` and provenance/citations; never `held_assets` or `candidate_assets`.
## 2. Clearance
### 2.1 Released asset required
A reusable asset must also appear in `released_assets` with a release-candidate clearance state.
### 2.2 Confidentiality permission required
Closeout's `released_assets` release-candidate state is the permission for internal engagement reuse. An explicit `confidentiality_permission` other than `cleared_for_internal_engagement_reuse` excludes the item.
### 2.3 Draft not publish
Release candidates remain draft knowledge for practice review. Items with `review_required` true (or absent) are labelled `pending_practice_review`: reference the title and citation only until Knowledge Management confirms.
### 2.4 Lessons need a governed rewrite state
A lesson is matched only when `rewrite_required` is explicitly false; its drafting guidance is used, never source text.
## 3. Matching
### 3.1 Relevance is deterministic
Relevance is computed from token overlap.
### 3.2 Sources travel with digest
Every item carries source, confidence, provenance and citations.
