# `resume_tool` MCP Tool — Black‑Box Usability Evaluation Report

## Executive Summary

Across full CRUD coverage of the tool surface (resume documents, basics, all section item types, and exports), the dominant usability blocker is **schema non-round‑trippability**: some endpoints historically accepted one set of field names but returned a different set. This breaks the standard agent loop of *read → modify JSON → write*, and it is particularly harmful for small/self-hosted models that rely heavily on copying prior tool outputs.

Second, the tool’s **declared input types (many `... | null`) do not match backend validation** for creates: numerous “optional” string fields reject `null` (must be a string; empty string is accepted). Combined with (observed) wrapper behavior that often serializes missing optionals as `null`, this causes repeated 400s and forces agents into trial-and-error.

High-impact redesign recommendations:
1) **Unify request/response schemas** (or translate both directions) and guarantee round-trip;  
2) **Fix optional/null semantics** (omit unset fields; don’t send nulls unless backend supports them);  
3) **Add response modes** (return only changed item/IDs by default; avoid returning entire lists / entire resume);  
4) **Standardize errors** into structured `{code,message,details,httpStatus}` rather than stringified HTTP blobs;  
5) **Fix `doc.delete` correctness** (don’t return `"None"` and don’t “succeed” on non-existent IDs without signaling).

---

## Testing Protocol

### Black-box approach
- Treated the tool strictly as an external API surface: only invoked the MCP functions provided.
- Created multiple resumes to test diverse states:
  - **Sample-data resume** (`with_sample_data=true`) to exercise update/delete against existing section items.
  - **Empty resume** (`with_sample_data=false`) to test empty-list behavior and minimal creation flows.
  - **Null/required-field probe resume** to systematically discover which “optional” fields actually reject `null`.

### Coverage
- **All exposed functions were invoked at least once**, including:
  - Resume doc endpoints: `list/get/create/update/delete`
  - Export endpoints: `export.pdf`, `export.screenshot`
  - Basics endpoints: `basics.get/create/update/delete`
  - All section endpoints for: award, certification, experience, education, project, profile, publication, skill, language, interest, volunteer, reference (`list`, `item.create`, `item.update`, `item.delete`)
- Negative and edge cases:
  - invalid `sort`, duplicate `slug`, invalid `resume_id`, invalid `item.id`, missing required args (`item_ids=null`, `items=null`)
  - `doc.update` with unsupported fields and with partial `data` replacement

### Cleanup
- Deleted all test resumes created during evaluation.

---

## API Complexity Analysis (esp. for Small/Self‑Hosted Models)

### 1) Endpoint count + repetitive yet inconsistent patterns
There are ~55 callable operations. While section CRUD is structurally repetitive, the **field naming and validation rules differ per section**, so “learn once, apply everywhere” fails—exactly the kind of pattern brittleness that smaller models struggle with.

### 2) Round-trip breakage: output schema ≠ input schema
A small model commonly:
1) calls `*.list` to fetch JSON
2) edits one or two fields
3) calls `*.item.update` with that JSON

This tool frequently makes that impossible because the **returned JSON cannot be directly fed back**:
- returned JSON uses one set of keys, but update endpoints validate against a different set of keys

For resource-constrained models, maintaining a custom mapping table across 11 section types is a major error source.

### 3) “Optional null” fields frequently reject `null` on create
The tool’s manifest advertises many fields as `string | null`, but the backend commonly responds with:
- `Invalid input: expected string, received null`

This forces agents to learn an undocumented rule: **send empty strings instead of null** for many create-only fields. Smaller models will repeatedly attempt `null` (because it matches the schema) and loop on errors.

### 4) Response verbosity overload
Many operations return **the entire section list** after any create/update/delete. `doc.update` returns the **entire resume** (potentially huge). For small-context models:
- IDs needed for follow-up operations may scroll out of context
- repeated large responses increase token pressure and failure rate
- self-hosted models with smaller context windows will truncate and lose critical state

### 5) Error handling is not agent-friendly
Errors appear in multiple incompatible shapes:
- `"HTTP 400: {...json...}"` as a *string* (agent must parse embedded JSON)
- Pydantic multi-line errors (human-oriented, verbose)
- tool-level plain strings: `"item_ids is required"`

Smaller models often cannot reliably parse these mixed formats into a stable remediation strategy.

---

## Observed Issues Table

| Issue ID | Reasoning/Analysis (Step-by-Step) | Description | Impact (esp. Small/Self‑Hosted Models) | Recommended change |
|---:|---|---|---|---|
| 1 | 1) Called a section create endpoint with a non-canonical key as suggested by documentation.<br>2) Response returned canonical keys.<br>3) Attempting read→edit→write using returned JSON failed or required manual mapping. | **Non-round‑trippable schemas**: request field names differ from response field names. | **High**: small models heavily rely on copying tool outputs; mapping tables increase hallucination/error risk and force extra tool calls. | Make all endpoints **return the same schema they accept** (canonical). If internal schema differs, translate responses too (not just requests). |
| 2 | 1) Tried `education.item.create` with `grade:null` (schema says nullable).<br>2) Backend returned `expected string, received null`.<br>3) Similar failures reproduced across multiple sections and fields.<br>4) Empty strings succeed. | **Declared optional/nullable fields are effectively required to be strings** on create; backend rejects `null` for many “optional” strings. | **High**: small models will follow the manifest and send nulls → repeated 400 loops. | Fix schemas to match reality: mark required fields required; remove `| null` where backend rejects it. Alternatively, wrapper should **omit absent fields** (don’t serialize them as null) or auto-coerce `null→""` where appropriate. |
| 3 | 1) Omitted `grade` in `education.item.create` request.<br>2) Backend still complained about `grade` being null.<br>3) Indicates wrapper likely fills missing optionals with null (or backend defaults to null but forbids). | **Wrapper likely serializes missing optional fields as `null`**, making omission impossible and triggering backend validation errors. | **High**: even “smart” agents that try to omit fields still fail; tiny models can’t infer wrapper serialization behavior. | Change wrapper serialization to **send only provided keys** (true optional fields). Prefer JSON Merge Patch semantics for updates and sparse objects for creates. |
| 4 | 1) `doc.create(with_sample_data=true)` returned a very large resume object.<br>2) `doc.update` returns the entire resume again.<br>3) All section CRUD returns full section lists. | **Over-verbose responses by default** (full resume / full lists returned). | **High**: context overflow, ID loss, higher cost/latency; self-hosted models truncate easily. | Add `response_mode` (e.g., `compact` default) to return only `{id, changedFields}` or created item(s). Provide explicit `return_full=true` option. Add pagination for lists. |
| 5 | 1) Tried `doc.update` with payload containing `data` partial object.<br>2) Backend returned many “expected object, received undefined” errors.<br>3) `doc.get` does not return the shape required to construct the full replacement. | `doc.update` has a **full-data replacement trap**: providing `data` triggers strict “replace everything” validation with an internal schema that is not discoverable from `doc.get`. | **Medium–High**: agents will try to patch via doc.update and get unhelpful floods of validation errors. | Split into two endpoints: `resume.metadata.update` (safe) and `resume.data.replace` (explicit full replace). Or provide a real `resume.data.patch` that supports sparse updates and uses the same shape returned by `doc.get`. |
| 6 | 1) Observed three distinct error encodings: plain strings, Pydantic text, and `"HTTP 400: {...}"` string with embedded JSON.<br>2) Agents must implement custom parsing heuristics. | **Inconsistent error envelope**; errors are often **stringified** and not machine-structured. | **High**: small models cannot reliably parse and recover; self-hosted agents often lack robust JSON extraction. | Standardize errors: `{status:"error", httpStatus, code, message, issues:[{path, expected, received}]}`. Parse backend errors into this structure (don’t return as string). |
| 7 | 1) Called `doc.delete` on an already-deleted resume ID → success.<br>2) Called `doc.delete` on a never-existing all-zero UUID → success.<br>3) Response is `"None"` (string). | **Delete is overly idempotent and misleading** (succeeds on non-existent IDs) and returns `"None"` string. | **Medium**: agents cannot detect wrong IDs; may think cleanup succeeded; debugging is harder. | Return structured result `{deleted:true/false}` and optionally 404 on unknown ID. Ensure JSON `null`, not string `"None"`. |
| 8 | 1) Experience/project/education/publication summaries were wrapped into `<p>...</p>` automatically.<br>2) Award/certification/reference descriptions returned without HTML wrapping.<br>3) Mixed HTML/plain appears across sections. | **Inconsistent rich-text normalization**; some endpoints inject HTML, others don’t. | **Medium**: models may generate HTML unintentionally; downstream renderers inconsistent; hard for small models to predict. | Pick one: store/return plain text or Markdown; if HTML is required, apply consistently and add `contentType` metadata. |
| 9 | 1) `basics.update` with `name:null` did not clear the field (ignored).<br>2) Only `basics.delete` clears all basics fields at once.<br>3) For sections, `null` means no-op; clearing requires empty array/string (undocumented). | **No consistent “clear field” semantics** (null = ignore, empty array = clear for some fields; basics can only be fully reset). | **Medium**: agents can’t reliably “remove” data; small models will guess and produce wrong behavior. | Add explicit clearing semantics (e.g., `clear_fields:["summary","url"]` or JSON Patch operations). Document: `null` vs `""` vs `[]`. |
| 10 | 1) `doc.list` returns `isPublic` and `isLocked`.<br>2) `doc.update` rejects `isPublic` as “extra forbidden”. | **Metadata exposed but not mutable** via tool (or missing endpoints). | **Low–Medium**: agents may plan workflows around publish/lock but can’t execute. | Provide `resume.visibility.update` / `resume.lock.update` or allow these fields in `doc.update`. |
| 11 | 1) Created a profile item with custom id `"custom-id-123"`; backend accepted it.<br>2) No validation or namespace guarantees observed. | **Arbitrary user-provided IDs accepted**; collision risks and inconsistent expectations (UUID vs free-form). | **Low–Medium**: agents may accidentally reuse IDs; small models may generate unstable IDs. | Prefer server-generated IDs only; if accepting custom IDs, validate format + enforce uniqueness per section. |
| 12 | 1) Tool descriptions mention fields/behavior (“hidden forced false”) that are not visible in responses.<br>2) Some manifest field names don’t match actual backend requirements. | **Documentation/manifest drift** relative to runtime behavior. | **High** when relying on schema for automation; small models depend heavily on manifest correctness. | Auto-generate MCP schemas from backend OpenAPI/JSONSchema; add contract tests ensuring manifest matches backend validation. |

---

## Redesign Proposals (Actionable + Prescriptive)

### 1) Canonical “agent-safe” schema + bidirectional translation layer
**Reasoning steps**
1) The tool already seems to translate *some inputs* into the upstream format.
2) If outputs are not translated back, agents are forced to learn upstream/internal names.
3) Round-trip fails and is the biggest recurring usability issue.

**Proposal**
- Define a canonical external schema (pick one and commit) and ensure tools both accept and return it.
- Implement translation in both directions:
  - request: external → internal
  - response: internal → external

**Benefit**
- Enables reliable read→modify→write workflows; dramatically reduces small-model failures.

---

### 2) Fix optional/null semantics: sparse payloads only, no auto-null filling
**Reasoning steps**
1) Backend rejects null for many create fields.
2) Even omitting fields still resulted in backend seeing null (observed).
3) Agents cannot predict which fields require empty string vs null.

**Proposal**
- Wrapper must send **only keys explicitly provided by the agent**.
- For create endpoints, optionally provide a `strict=false` mode that auto-fills missing required strings with `""` *server-side* (not agent-side), but only if that is truly desired.
- Update MCP schemas to match backend requirements (remove `| null` where invalid).

**Benefit**
- Eliminates a large class of 400 loops and makes the manifest trustworthy for automation.

---

### 3) Response modes + delta responses (default compact)
**Reasoning steps**
1) Many endpoints return full lists/resumes.
2) Small/self-hosted contexts overflow; agents lose IDs.

**Proposal**
Add a common optional parameter across endpoints:
- `response_mode: "compact" | "full"` (default `"compact"`)

Examples:
- `*.item.create` in compact mode returns `{created:[{id,...}], sectionCount:n}`
- `*.item.update` returns `{updated:[{id, changedFields...}]}`
- `*.item.delete` returns `{deleted:[ids], remainingCount:n}`

**Benefit**
- Keeps tool calls within small-context budgets and improves multi-step reliability.

---

### 4) Standardize errors into structured objects (no stringified HTTP blobs)
**Reasoning steps**
1) Current errors require parsing strings; inconsistent formats.
2) Smaller models are brittle at extracting JSON out of text.

**Proposal**
- Always return:
```json
{
  "status": "error",
  "httpStatus": 400,
  "code": "INVALID_PATCH",
  "message": "Input validation failed",
  "issues": [{"path": "...", "expected": "string", "received": "null"}]
}
```
- Map backend and Pydantic exceptions into this envelope.

**Benefit**
- Enables deterministic agent recovery strategies and dramatically improves small-model compatibility.

---

### 5) Separate safe metadata update from dangerous full `data` replacement
**Reasoning steps**
1) `doc.update` currently supports metadata updates and also a “replace all data” mode via `data`.
2) The latter is not discoverable and produces huge error floods.

**Proposal**
- `resume.doc.update` should only allow: `name`, `slug`, `tags`, (and optionally `isPublic`, `isLocked`).
- Create explicit endpoints:
  - `resume.data.replace(resume_id, data_full)` (requires full schema)
  - `resume.data.patch(resume_id, ops)` (JSON Patch / Merge Patch)

**Benefit**
- Prevents accidental destructive or impossible updates; clearer mental model for all agents.

---

### 6) Normalize text fields and declare `contentType`
**Reasoning steps**
1) Some endpoints wrap summaries into HTML; others return plain strings.
2) Agents cannot predict or control formatting.

**Proposal**
- Store and return Markdown (or plain text) consistently.
- Add `contentType: "text/plain" | "text/markdown" | "text/html"` per rich text field (or per section).

**Benefit**
- Consistent rendering; agents can generate correct content without guesswork.

---

### 7) Add “schema introspection” helper endpoint for agents
**Reasoning steps**
1) Required fields differ per section and are not correctly captured by the manifest.
2) Self-hosted agents often prefer runtime schema discovery to avoid hardcoding.

**Proposal**
- Add: `resume.section.schema.get(sectionName)` returning:
  - canonical field names (input/output)
  - required-on-create fields
  - nullability rules
  - clear semantics (null vs empty)

**Benefit**
- Improves robustness for weaker models and reduces repeated 400 retries.

---

## Appendix

### A) Coverage Matrix (All MCP functions exercised)

- `resume.doc.*`: list/get/create/update/delete ✅  
- `resume.export.*`: pdf/screenshot ✅  
- `resume.basics.*`: get/create/update/delete ✅  
- Section CRUD ✅ for:  
  - award, certification, experience, education, project, profile, publication, skill, language, interest, volunteer, reference

---

### B) Selected Raw Transcripts / Error Logs (Representative)

#### B1) Invalid enum validation (good)
**Input**
```json
{"tags":[],"sort":"invalidSortKey"}
```
**Output**
```json
{
  "status":"error",
  "error":"HTTP 400: ... 'Invalid option: expected one of \"lastUpdatedAt\"|\"createdAt\"|\"name\"' ..."
}
```

#### B2) Duplicate slug (good)
**Input**
```json
{"name":"Dup Slug","slug":"mcp-resume-tool-eval-2026-02-09","tags":["mcp_test"],"with_sample_data":false}
```
**Output**
```json
{"status":"error","error":"HTTP 400: ... 'RESUME_SLUG_ALREADY_EXISTS' ..."}
```

#### B3) Schema mismatch example (section item)
When documentation implies an alternate key, strict tool validation rejects it or responses become non-round-trippable unless translation is implemented in both directions.

#### B4) Create rejects null for “optional” field (education.grade)
**Input**
```json
{"items":{"id":null,"school":"Test U","degree":"MSc","area":"HCI","grade":null,"location":"Online","period":"2020-2022"}}
```
**Output**
```json
{
  "status":"error",
  "error":"HTTP 400: ... INVALID_PATCH ... expected string, received null ... /education/items/1/grade"
}
```

#### B5) `doc.update` with `data` partial triggers full replacement validation flood
**Input**
```json
{"payload":{"data":{"sections":{"basics":{"name":"Replaced Via Data"}}}}}
```
**Output (excerpt)**
```json
{
  "status":"error",
  "error":"HTTP 400: ... INVALID_PATCH ... expected object, received undefined ... /data/picture ... /data/customSections ..."
}
```

#### B6) Delete succeeds for non-existent ID + returns `"None"`
**Input**
```json
{"resume_id":"00000000-0000-0000-0000-000000000000"}
```
**Output**
```json
{"status":"success","response":"None"}
```

#### B7) Patch target not found (good but stringified)
**Input**
```json
{"items":{"id":"does-not-exist","name":"Nope"}}
```
**Output**
```json
{
  "status":"error",
  "error":"HTTP 404: ... 'PATCH_TARGET_NOT_FOUND' ..."
}
```

---

### C) Observed input→output key mismatches (historical)
When request/response keys differ, the mapping is not exposed as an explicit contract, forcing agents to infer it.