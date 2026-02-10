## Executive Summary
`resume_tool` is functionally broad (resume CRUD, section CRUD across 12 section types, and PDF/screenshot export) and generally responds quickly with predictable “success/error” envelopes. However, agent usability—especially for small/self-hosted models—is significantly impacted by (1) an extremely large tool surface (≈58 endpoints with repeated patterns), (2) inconsistent update semantics that can silently **delete data** (most notably `summary` vs `highlights` fields), (3) schema/documentation mismatches (e.g., “website” alias) that trigger **client-side validation failures**, and (4) inconsistent response conventions (HTML vs plain text, “None” string, delete returning “remaining items”).

High-level recommendations:
- Collapse the section APIs into a **generic** section endpoint, add **response shaping** (minimal vs full, field selection), and add **pagination**.
- Standardize update semantics to true **PATCH/merge** behavior (omitted fields unchanged; explicit `null` clears).
- Enforce **server-generated unique IDs** (or at minimum enforce uniqueness if client IDs are allowed).
- Standardize naming (snake_case vs camelCase), rich-text handling, and error envelopes (including tool-schema validation errors).

---

## Testing Protocol
### Approach
Black-box testing was performed exclusively through the documented MCP tool functions (no assumptions about backend implementation). I created and deleted multiple temporary resumes to avoid mutating existing data and used unique tags/slugs for filtering.

### Coverage
1. **Resume-level ops**
   - `resume.doc.list` (with/without sort, tag filtering)
   - `resume.doc.create` (`with_sample_data` true/false)
   - `resume.doc.get`
   - `resume.doc.delete` (existing + non-existent UUID)
2. **Export**
   - `resume.export.pdf`, `resume.export.screenshot` (valid + invalid resume_id)
3. **Basics CRUD**
   - `resume.basics.get`, `.create`, `.update`, `.delete`
   - Schema mismatch test: `payload.website` alias claim
4. **All section CRUDs (12 section types)**
   - For each section: `list`, `item.create`, `item.update`, `item.delete`
   - Both **single-item** and **batch** create/update forms
5. **Edge cases / error handling**
   - Invalid UUID format
   - Non-existent UUID
   - Missing required `item.id` for update
   - `items=null`, `item_ids=null`
   - Duplicate slug
   - Schema validation failures raised before tool call dispatch
6. **Security/config check**
   - Inspected uploaded `servers.json` MCP config file for operational/security implications (token **redacted** in this report).

---

## API Complexity Analysis (focus: small/self-hosted models)
### Surface Area & Cognitive Load
- The tool exposes ~**58** callable operations (resume CRUD + export + basics CRUD + 12 sections × 4 ops).  
- Many functions differ only by section name, but require the model to select the correct function name and correctly construct slightly different schemas.

**Impact on small/self-hosted models (e.g., 5‑nano, Ollama-class):**
- Tool-selection becomes a major failure mode: smaller models often mis-pick among near-duplicate tool names.
- The schemas are verbose and nested; errors are easy to make (e.g., wrong field name, wrong union branch).

### Union Inputs & Inconsistent Response Shapes
- `items` accepts either an object or an array; responses typically return arrays even for single-item input.
- `item_ids` accepts either a string or a string array.
- Deletes appear to return “remaining items” (not “deleted items”), but this is not explicit.

Small models are disproportionately hurt by union/overloaded parameters because:
- They must branch on runtime type in their “mental program.”
- They frequently “mirror” the input shape (object in → object out) and get confused when the output is always list-like.

### Large Payloads & Context Window Pressure
- `resume.doc.create(with_sample_data=true)` returns a **very large** nested resume document (dozens of items across many sections).
- `resume.doc.get` returns the full resume with all sections (even if the agent only needs IDs or one section).

Small/self-hosted models often operate with limited context windows and memory; oversized responses degrade:
- Reliability of subsequent tool calls (IDs lost or overwritten)
- Risk of hallucinated edits because the model can’t retain full state

### Update Semantics Are Not Uniform (and can be destructive)
The single largest usability hazard observed: for several sections, updating `summary` clears `highlights`, and updating `highlights` clears `summary`. This forces multi-step “read-modify-write with full object retention,” which is difficult for resource-constrained agents.

### Schema/Docs Mismatch Causes Hard Failures
Some failures happen *before the tool call* due to strict schema validation (“extra inputs forbidden”), which produces a different error format than backend errors. Small models typically do not recover well unless the error message provides a direct fix.

---

## Observed Issues Table

| Issue ID | Reasoning/Analysis (Step-by-Step) | Description | Impact (esp. Small/Self-Hosted Models) | Recommended Change |
|---:|---|---|---|---|
| 1 | 1) Tried `resume.doc.list` with `tags=null` expecting optional tags. 2) Tool call failed client-side with Pydantic validation error requiring a list. 3) This contradicts the parameter description (“Optional list of tags”). | **`resume.doc.list.tags` is required** by schema even though docs imply optional. Must pass `[]`. | **High**: small models often omit “optional” args; client-side hard failure prevents graceful recovery. | Make `tags` truly optional (nullable/omittable) in schema; default to `[]` server-side. Ensure validation errors return the same envelope as runtime errors. |
| 2 | 1) `resume.basics.update` docs claim `url` accepts alias `website`. 2) Called with `payload.website`. 3) Tool rejected with “extra inputs are not permitted”. | **Docs claim `website` alias, but schema forbids it.** | **High**: many resume schemas use `website`; small models will guess it and repeatedly fail. | Add `website` alias at schema layer (or remove claim). Ideally accept both `url` and `website` and normalize. |
| 3 | 1) Created experience/education/project/publication/volunteer items with both `summary` and `highlights`. 2) Updated only `highlights`. 3) Observed `summary` became `null`. 4) Updated only `summary`. 5) Observed `highlights` became `null`. | **Destructive partial updates for (`summary`, `highlights`) pairs** in multiple sections. Updating one field clears the other. | **Very High**: silent data loss; small models won’t reliably fetch+replay full objects, and will corrupt resumes. | Implement consistent PATCH semantics: omitted fields unchanged; explicit `null` clears. Add regression tests for “update highlights preserves summary” and vice versa. |
| 4 | 1) Observed `resume.basics.update` behaves like patch (omitted fields preserved). 2) Observed section item updates vary: some patch-like, some destructive for specific fields. | **Update semantics inconsistent across endpoints and fields.** | **High**: models learn wrong rule from one endpoint and apply to others, causing accidental data loss. | Define and document one update contract for all endpoints (e.g., JSON Merge Patch). Enforce uniformly. |
| 5 | 1) Created experience/project/etc with plain-text `summary`. 2) Responses often returned HTML wrapped in `<p>…</p>`. 3) In awards/certs/references, summary remained plain. 4) Sample data sometimes contained HTML already. | **Inconsistent rich-text behavior** (some summaries HTML-wrapped, others plain). | **Medium–High**: small models may double-wrap HTML, strip tags incorrectly, or fail downstream rendering. | Standardize: either (a) always store/return plain text + separate `summary_html`, or (b) always accept/return HTML with clear contract and sanitization rules. |
| 6 | 1) Created skill with user-specified `id="custom-id-123"`. 2) Created another skill with **same ID**. 3) Tool accepted duplicates. 4) Update/delete by id affected only the “first match”. | **Client-supplied IDs are allowed and not unique**, causing ambiguous update/delete behavior. | **Very High**: breaks referential integrity; small models rely on IDs as unique keys. | Disallow client-specified IDs (server generates UUIDs) *or* enforce uniqueness within resume+section. Reject duplicates with clear error code. |
| 7 | 1) Noted many endpoints accept `items` as object or list. 2) Even when sending an object, response is a list. | **Overloaded input shapes** (object vs array) + list-only outputs increase parsing burden. | **Medium**: small models are brittle with union types; they often assume output mirrors input. | Accept only arrays for batch endpoints (even single item), or provide separate `item.create_one` returning a single object. Keep I/O shapes symmetric. |
| 8 | 1) Deleted a resume; tool returned `{"status":"success","response":"None"}`. 2) Deleting a non-existent UUID also returned success `"None"`. | **Delete response is ambiguous** (`"None"` string; idempotency not documented). | **Medium**: agents cannot confirm deletion or distinguish “didn’t exist” vs “deleted”. | Return structured result: `{deleted: true/false, existed: true/false}`. Use JSON `null` not `"None"`. |
| 9 | 1) Invalid UUID format returns friendly error. 2) Non-existent UUID on `get` returns stringified HTTP dict. 3) Schema validation errors bypass tool envelope entirely (“Failed to call MCP tool…”). | **Error handling not uniform** across validation vs runtime vs HTTP errors. | **High**: small models fail to implement robust retries/repairs without consistent machine-readable error codes. | Standardize all errors to a single envelope: `{ok:false, code, message, details, hint}`. Wrap schema validation errors similarly. |
| 10 | 1) `doc.create(with_sample_data=true)` returned a huge nested resume. 2) For small models, this consumes context and makes follow-up operations unreliable. | **Oversized default responses** (no “minimal” response mode). | **High** for small models: context overflow → ID loss → wrong updates. | Add response shaping: `return="id_only"|"metadata"|"full"`, plus section include/exclude filters. Make “minimal” default for tool use. |
| 11 | 1) `resume.doc.list` returns all matches with no paging parameters. 2) In environments with many resumes, response becomes huge. | **No pagination/limits on list endpoints.** | **High**: overwhelms small models; also wastes tokens/time. | Add `limit`, `offset/cursor`, and `total` fields. Provide `next_cursor`. |
| 12 | 1) Observed mixed naming conventions: requests use `with_sample_data`, `resume_id`; responses include `createdAt`, `updatedAt`, `isPublic`. | **Inconsistent naming conventions** across request/response payloads. | **Medium**: increases mapping errors, especially for small models. | Adopt one convention end-to-end (prefer snake_case for MCP tools) or provide consistent aliases in both directions. |
| 13 | 1) Inspected uploaded MCP config file. 2) File contains a bearer token in plaintext. | **Operational security risk**: long-lived token in config file. | **Context-dependent but potentially High** if shared or checked into repos. | Use env vars / secret managers; prefer short-lived tokens. Provide guidance and “redaction safe” examples. |

---

## Redesign Proposals (actionable)
### Proposal A — Collapse Section CRUD into a Generic API (major usability win)
**Rationale (reasoning-first):**
1. Today, the model must choose among dozens of near-identical endpoints (e.g., `resume.section.project.item.update` vs `resume.section.publication.item.update`).  
2. Small models frequently mis-select tools when names are similar.  
3. The payload shapes are also similar, so duplication is pure cognitive overhead.

**Change:**
- Replace the 48 section endpoints with 4 generic endpoints:
  - `resume.section.list(resume_id, section)`
  - `resume.section.create(resume_id, section, items[])`
  - `resume.section.update(resume_id, section, items[])`
  - `resume.section.delete(resume_id, section, item_ids[])`

**Benefits:**
- Dramatically reduces tool-selection error rate for small models.
- Simplifies code generation, docs, and testing.

---

### Proposal B — Enforce True PATCH Semantics Everywhere (fix data loss)
**Rationale:**
1. Agents assume “update only changes the fields I provide.”  
2. Current behavior violates that assumption for (`summary`, `highlights`) and possibly other field pairs.  
3. This causes silent corruption and requires multi-turn fetching + replaying full objects (hard for small models).

**Change:**
- Adopt JSON Merge Patch semantics:
  - **Omitted key**: leave unchanged
  - **Key with `null`**: explicitly clear
  - **Key with value**: set
- Ensure all section `item.update` implementations use the same `exclude_unset`/merge behavior, including rich-text fields.

**Benefits:**
- Eliminates silent data loss.
- Allows safe single-field updates without extra reads.

---

### Proposal C — Make IDs Server-Generated + Uniqueness-Enforced
**Rationale:**
1. IDs are used as stable handles for update/delete.  
2. Allowing client-chosen IDs without uniqueness breaks the handle model.  
3. Observed duplicates lead to “first match wins” behavior (ambiguous & dangerous).

**Change options:**
- Preferred: ignore client `id` on create; always generate UUID.
- If client IDs must be allowed: enforce uniqueness within (resume_id, section). Reject duplicates with `code="DUPLICATE_ITEM_ID"`.

**Benefits:**
- Makes automation reliable and deterministic.

---

### Proposal D — Response Shaping + Pagination (small-model compatibility mode)
**Rationale:**
1. Large payloads quickly exceed small model context limits.  
2. Many operations only need IDs/metadata, not full nested sections.  
3. No pagination on list endpoints is a scaling footgun.

**Change:**
- Add `return` or `view` param for create/get/list endpoints:
  - `id_only`, `metadata`, `full`
- Add `include_sections` / `exclude_sections` for `doc.get`.
- Add `limit`, `cursor`, `next_cursor`, `total` to list endpoints.

**Benefits:**
- Keeps tool interactions within small-context budgets.
- Improves performance and reduces token spend for all models.

---

### Proposal E — Standardize Rich Text Handling
**Rationale:**
1. Mixed HTML/plain behavior causes accidental formatting bugs.  
2. Agents need deterministic contracts for sanitization and rendering.

**Change:**
- Choose one:
  - **Option 1:** store plain text only; render HTML downstream.
  - **Option 2:** store sanitized HTML, but always return both `summary_text` and `summary_html`.
- Document allowed tags, sanitization behavior, and whether `<p>` wrapping is applied.

**Benefits:**
- Predictable formatting and easier downstream integration.

---

### Proposal F — Unify Error Envelopes (including schema validation errors)
**Rationale:**
1. The system currently emits at least three error “styles”: tool schema validation failures, `{status:"error"}`, and stringified HTTP dictionaries.  
2. Small models need structured `code` + `hint` to repair calls reliably.

**Change:**
- Always return:
  ```json
  { "ok": false, "code": "...", "message": "...", "details": {...}, "hint": "..." }
  ```
- Wrap schema validation errors into the same structure (instead of failing the tool call).

**Benefits:**
- Easier automatic recovery, retries, and promptless repair loops.

---

## Appendix (Selected Raw Transcripts / Logs)

### A1) MCP server config (uploaded file) — **token redacted**
```json
{
  "mcpServers": {
    "resume-tool": {
      "type": "streamable-http",
      "authorization": "Bearer <REDACTED>",
      "url": "https://m.earthperson.org/mcp"
    }
  }
}
```

### A2) `resume.doc.list` requires `tags` to be a list
**Input**
```json
{"tags": null, "sort": null}
```
**Output (client-side validation error)**
```text
Input should be a valid list
```

### A3) Docs mismatch: `payload.website` rejected (despite alias claim)
**Input**
```json
{"resume_id":"...","payload":{"website":"https://example.com"}}
```
**Output**
```text
payload.website Extra inputs are not permitted
```

### A4) Data loss: updating `highlights` clears `summary` (experience example)
**Create**
```json
{"items":{"summary":"Did work.","highlights":["H1","H2"]}}
```
**Update highlights only**
```json
{"items":{"id":"...","highlights":["H1","H2","H3"]}}
```
**Observed output excerpt**
```json
{"summary": null, "highlights":["H1","H2","H3"]}
```

### A5) Symmetric data loss: updating `summary` clears `highlights`
**Update summary only**
```json
{"items":{"id":"...","summary":"Did more work."}}
```
**Observed output excerpt**
```json
{"summary":"<p>Did more work.</p>","highlights":null}
```

### A6) Duplicate client IDs accepted → ambiguous updates/deletes
**Create skill with custom id**
```json
{"items":{"id":"custom-id-123","name":"Go"}}
```
**Create another skill with same id**
```json
{"items":{"id":"custom-id-123","name":"Go2"}}
```
**List shows duplicates**
```json
[
  {"id":"custom-id-123","name":"Go"},
  {"id":"custom-id-123","name":"Go2"}
]
```

### A7) `resume.doc.delete` returns `"None"` string, and is idempotent for non-existent IDs
**Delete non-existent UUID**
```json
{"resume_id":"219636aa-9341-49d4-b5c4-25500b3888e7"}
```
**Output**
```json
{"status":"success","response":"None"}
```

### A8) Export returns direct URLs (example)
**Output excerpt**
```json
{"status":"success","response":{"url":"https://.../pdfs/<resume_id>/<file>.pdf"}}
```

---

If you want, I can also provide a “small-model-friendly” *idealized* v2 schema (single generic section endpoint + merge-patch semantics + minimal responses) as a concrete target for a rewrite.
