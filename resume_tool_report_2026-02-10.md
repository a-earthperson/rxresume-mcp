# `resume_tool` MCP — Black‑Box Usability Evaluation (Agent-Focused)
**Evaluation date:** Tuesday, **February 10, 2026**  
**Tool namespace tested:** `mcp_resume_tool` (all exposed endpoints)

---

## Executive Summary

This MCP tool provides a workable CRUD surface for resumes, basics, and section items, plus PDF/screenshot exports. In practice, however, it is **hard for automated agents (especially small/self-hosted models)** to use reliably because **the “real” schemas are not discoverable from the tool interface** and several behaviors are inconsistent or unexpectedly destructive. Agents are forced into a trial-and-error loop (“send JSON Resume-like payload → get `extra_forbidden` → guess the right field names”), which quickly becomes brittle for smaller models.

The highest-impact issues observed are: (1) **schema/typing mismatches** between the declared tool interface and actual behavior, (2) **section APIs with polymorphic item schemas but `any` typing**, (3) **responses that return entire section lists on every mutation**, inflating payloads and context usage, and (4) **inconsistent error shapes** (some errors are structured JSON; others are tool-call failures from Pydantic). Additionally, `export.screenshot` appears **cached/idempotent**, potentially returning **stale images after edits**, while `export.pdf` regenerates each call.

High-level recommendations:
1. **Introduce schema introspection and/or section-specific typed tools** (or a strongly typed union schema) so agents can construct correct payloads without guessing.
2. **Standardize error envelopes** (including Pydantic validation failures) and include error paths like `items[1].rating`.
3. Add **delta-return modes** (`return=created|updated|all`) to keep outputs small.
4. Fix/clarify **list-field semantics** (avoid `[] → null`, avoid destructive replace defaults).
5. Add **metadata patching** (rename resume, edit tags, visibility/lock) and improve delete semantics.

---

## Testing Protocol

### Coverage goals
I tested the tool as a black box, focusing on:
- End-to-end CRUD flows for resumes and sections.
- Validation behavior and error handling.
- Edge cases that are common failure modes for small/self-hosted agents (wrong type, missing fields, wrong schema assumptions).
- Response size/verbosity and state requirements (IDs, full-list returns).
- Export behavior (PDF/screenshot) consistency.

### Procedures executed (representative)
1. **Discovery & listing**
   - `resume.doc.list` with and without filters, with valid and invalid sort values, with missing arguments.
   - Verified tags filter semantics (AND vs OR).
2. **Resume lifecycle**
   - `resume.doc.create` (with/without tags, with “basics” provided).
   - `resume.doc.get` and `resume.basics.get`.
   - `resume.doc.delete` for existing, non-existing, and invalid IDs.
3. **Basics patching**
   - `resume.basics.patch` merge behavior, clearing fields, type validation (e.g., `location`).
4. **Section CRUD**
   - For each section type: `list → create → update → delete`.
   - Negative tests: unknown section names, wrong `items` type, empty lists, missing `id` on update, delete non-existent item ID.
   - Date format validation for `startDate/endDate`.
5. **Export**
   - `resume.export.pdf` and repeated calls to observe caching/regeneration.
   - `resume.export.screenshot` repeated calls to observe caching/staleness.

### Cleanup
Temporary test resumes created during the evaluation were deleted at the end to avoid persistent clutter.

---

## API Complexity Analysis (Small/Self-Hosted Model Lens)

### 1) Surface area is small, but “shape complexity” is high
The tool exposes ~12 operations, but the real complexity is in:
- **Polymorphic `resume.section.*`**: one endpoint handles many sections, each with its own schema.
- Item schemas are not embedded in the MCP tool type system (most are `any`), forcing inference.

For small models (e.g., “5‑nano” scale) this is a major problem:
- They have less capacity to run multi-step schema inference loops.
- They are more likely to hallucinate JSON Resume fields (`highlights`, `summary`, nested `location`) and then get rejected.
- Without an introspection endpoint, they must learn schemas via error messages, which are not always actionable.

### 2) Workflow requires state (IDs) and multi-turn coordination
Updates and deletes require the **server-generated UUIDs** for items. This implies an agent must:
1. Create item(s)
2. Parse response to capture new `id`s
3. Store those IDs reliably
4. Use them later for update/delete

Smaller models frequently fail at persistent ID tracking across long contexts—especially because mutation calls return full lists, pushing older context out.

### 3) Response payloads scale with section size (O(N))
`resume.section.create/update/delete` return the **entire section list** after mutation. That is:
- Useful in interactive UI contexts
- Risky for agents, because it inflates response size and context cost, and increases parsing burden.

For resumes with 50–200 items in a section (skills/work), this will become a major bottleneck for local models with smaller context windows.

### 4) Error handling is not uniform
I observed **two distinct classes of errors**:
- **Structured tool-level errors**: `{"status":"error","error":{...}}`
- **Tool invocation failures** (Pydantic validation): the tool call fails and returns a different “Failed to call MCP tool …” blob.

Small agents typically assume a single error schema; mixed error shapes increase retry loops and brittle glue code.

---

## Observed Issues Table

| Issue ID | Reasoning / Analysis (Step-by-Step) | Description | Impact (esp. Small/Self-Hosted Models) | Recommended Change |
|---:|---|---|---|---|
| 1 | 1) Called `resume.doc.create` with `basics` object despite tool definition suggesting `basics?: null`.<br>2) Call succeeded and returned `resume_id` plus `basics`.<br>3) This contradicts the exposed tool signature and can’t be inferred safely by agents. | **Tool interface type definitions do not match real behavior** (e.g., `doc.create.basics`, `doc.list.tags` optional defaults). | **High**: small models rely on tool schemas to form valid calls; mismatches cause repeated failures or missed capabilities. | **Regenerate MCP tool schemas from source** (single source of truth). Add automated contract tests ensuring displayed schemas match runtime validation. |
| 2 | 1) Tried creating `work` using common JSON Resume fields (`summary`, `highlights`).<br>2) Tool rejected with `extra_forbidden` for those fields.<br>3) Had to infer that the correct field is `description` and that `highlights` is unsupported. | **Section item schemas are undocumented and differ from common JSON Resume expectations.** | **High**: agents will predict JSON Resume fields and loop on validation errors; smaller models struggle to converge. | Provide **schema introspection** (`resume.section.schema(section)`) or implement **section-specific typed tools** (e.g., `work.create`, `work.update`). Also consider supporting JSON Resume aliases (`summary`→`description`). |
| 3 | 1) Observed `resume.section.create/update/delete` returning full section lists after each mutation.<br>2) With multiple items, response becomes large; also makes it harder to identify “what changed.” | **Mutations return full section lists (O(N) response growth).** | **High** for local models with limited context; also increases latency and parsing cost. | Add `return_mode` param: `delta` (created/updated/deleted IDs), `created_only`, `all` (current), `none`. Default to `delta` for agent-friendliness. |
| 4 | 1) Triggered wrapper-level validation errors (e.g., `resume.doc.list` with `tags:"pytest"`).<br>2) Tool invocation failed with a different error format than normal tool errors.<br>3) Other failures return `{"status":"error", ...}`. | **Inconsistent error envelopes** (Pydantic/tool-call failures vs structured tool errors vs upstream Reactive Resume errors). | **High**: small models often have simple “if status==error” logic and will mis-handle tool-call failures. | Catch and normalize wrapper validation into the same `{status:"error", error:{code,message,issues[]}}` structure. Include a stable `error.code` taxonomy. |
| 5 | 1) Called `resume.doc.delete` with a valid-but-nonexistent UUID (`0000…`).<br>2) Returned `status:"success", response:null` (silent no-op).<br>3) Meanwhile `section.delete` for missing item ID returns 404. | **Delete semantics inconsistent and potentially misleading** (resume delete is idempotent/no-signal; section delete errors). | **Medium–High**: agents may believe deletion succeeded and stop retrying, masking state bugs. | Return `{deleted:true}` vs `{deleted:false, notFound:true}` for resume deletion. Consider making section deletes idempotent too, or add `ignore_missing=true`. |
| 6 | 1) Observed `export.pdf` produces new URL each call (timestamped).<br>2) Observed `export.screenshot` returns same URL on repeated calls, even after edits earlier in the session. | **Export behavior inconsistent**; screenshot appears cached and may become stale. | **Medium**: agents generating “latest screenshot” may unknowingly serve stale artifacts. | Add `force=true` to screenshot export; return `{url, generatedAt, basedOnUpdatedAt}` to make staleness detectable. |
| 7 | 1) Patched `basics.location` with an object (JSON Resume-style).<br>2) Tool rejected: “location should be a valid string.” | **Field type choices diverge from common resume schemas** (location as string vs structured). | **Medium**: agents trained on JSON Resume will frequently send structured location objects. | Either (a) accept both string and object and normalize, or (b) rename to `locationText` and add `locationObject` support. Update tool schema/docs accordingly. |
| 8 | 1) `basics.profiles` appears in basics and also as a dedicated `profiles` section.<br>2) Patching `basics.profiles` with a new list replaced/deleted prior profiles.<br>3) Setting `profiles:[]` resulted in `profiles:null` and removed section entries. | **Profiles exist in two places with destructive replace semantics**; `[] → null` behavior is surprising. | **High**: easy for agents to accidentally delete user data by sending an incomplete profiles list. | Single source of truth: keep profiles only as `sections.profiles` (or only `basics.profiles`). If patching lists, support `merge/upsert` semantics by default; reserve full replace for explicit `replace=true`. Preserve empty arrays as `[]`. |
| 9 | 1) Attempted to use `section.update` with `clear` only (or with item containing only `id`).<br>2) Tool required at least one non-id field update (“No fields provided…”), so “clear only” wasn’t possible via `clear`. | **`clear` parameter is awkward/inconsistent**; cannot be used alone, and shape allows two formats (list or dict). | **Medium**: increases retries and complexity; small models struggle with optional complex params. | Simplify: allow `clear`-only updates; enforce one clear schema (e.g., `clear: {<id>: ["field"]}`). Or remove `clear` and standardize “set null/empty string to clear” with explicit docs. |
| 10 | 1) Created section items with `{}` (empty objects).<br>2) Tool accepted and created blank items with all-null fields. | **Create is overly permissive**, enabling accidental creation of empty items. | **Medium–High**: small models sometimes emit empty dicts due to tool-call formatting errors; this pollutes data. | Require at least one meaningful field on create (per section) OR add `allow_blank=true` default false. |
| 11 | 1) Batch update with multiple items where one had invalid type (e.g., `rating:"abc"`).<br>2) Error message reported `field:"rating"` without identifying which item failed (`items[1].rating`). | **Error paths are not specific enough for batch operations.** | **High**: small agents can’t reliably repair the correct sub-object; leads to repeated full retries. | Include precise JSON pointer paths: `items[1].rating`. Return all validation issues at once when possible. |
| 12 | 1) Tag filtering with `tags:["pytest","sample"]` returned only resumes containing both tags (AND).<br>2) Tags are case-sensitive; duplicates preserved. | **Tag semantics are non-obvious** (AND filter; case sensitive; duplicates allowed). | **Low–Medium**: causes unexpected empty results, extra tool calls. | Document filter semantics explicitly; optionally support `match=any|all` and normalize/dedup tags on create. |
| 13 | 1) Looked for a way to rename a resume or update tags after creation.<br>2) No tool method exists for resume metadata patching beyond basics/sections. | **Missing metadata mutation endpoints** (rename, tags, visibility/lock). | **Medium**: agents can’t complete common automation workflows; must create new resumes instead. | Add `resume.doc.patch` for `{name,tags,isPublic,isLocked}` with safe validation and tag normalization. |

---

## Redesign Proposals (Prescriptive)

### Proposal A — Add schema introspection and make schemas first-class
**Reasoning (observed):**
- Agents must guess each section’s item shape; tool types use `any`.
- Trial-and-error is costly and fails more often for small models.

**Design:**
- Add: `resume.section.schema.get(section)` returning JSON Schema (or a compact typed descriptor):
  - allowed fields, types, optional/required, example payloads
  - validation rules (e.g., ISO date formats)
- Add: `resume.tool.version.get()` returning `schemaVersion`, `toolVersion`.

**Benefits:**
- Eliminates “guess-and-fail” loops.
- Enables deterministic payload construction and programmatic validation, especially for local agents.

---

### Proposal B — Replace the generic section endpoints with section-specific typed tools (or a strict union schema)
**Reasoning (observed):**
- `resume.section.create/update/delete` are polymorphic by `section`, but MCP typing can’t express that easily without help.
- Smaller models do better with simpler, explicit tools.

**Design option 1 (preferred for small models):**
- Provide tools like:
  - `work.create({resume_id, items: WorkItemInput[]})`
  - `education.update({resume_id, items: EducationItemPatch[]})`
- Each tool has strongly typed arguments.

**Design option 2 (single tool, still typed):**
- Keep `resume.section.create`, but define `items` as a `oneOf` union keyed by `section`, with explicit schemas per section.

**Benefits:**
- Reduces schema ambiguity and hallucinated fields.
- Improves tool-call success rates on smaller/self-hosted models.

---

### Proposal C — Standardize response envelopes + add delta modes
**Reasoning (observed):**
- Returning full lists scales poorly and forces diffing.
- Agents mostly need created IDs and a small confirmation.

**Design:**
- For all mutations return:
  ```json
  {
    "ok": true,
    "resume_id": "...",
    "section": "skills",
    "result": {
      "created": [{...}],
      "updated": [{...}],
      "deleted": ["..."],
      "all": null
    }
  }
  ```
- Add `return_mode`: `delta` (default), `all`, `none`.

**Benefits:**
- Smaller responses; better for short-context models.
- Easier to capture IDs of newly created items reliably.

---

### Proposal D — Normalize and unify error handling (including Pydantic wrapper failures)
**Reasoning (observed):**
- Two-layer validation produces multiple error shapes.
- Upstream errors contain nested noise; tool-level errors omit item indexes.

**Design:**
- Always return a structured error:
  ```json
  {
    "ok": false,
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "...",
      "issues": [
        {"path":"items[1].rating","type":"float_parsing","message":"..."}
      ]
    }
  }
  ```
- Wrap Pydantic tool-argument errors into this same format.

**Benefits:**
- Agents can implement one retry/repair strategy.
- Better automatic correction loops for small models.

---

### Proposal E — Make list-field semantics safe and explicit (no implicit destructive replace)
**Reasoning (observed):**
- `profiles` can be mutated via basics patch and via section endpoints, with replace-like behavior.
- Empty lists often become `null`, which removes representational distinction.

**Design:**
- Preserve empty arrays as `[]`.
- For list fields, default semantics should be:
  - `add`: append items
  - `update`: patch by id
  - `remove`: by id
- If full replace is needed, require explicit `replace=true`.

**Benefits:**
- Prevents accidental data loss.
- More intuitive for automation and safer for constrained models.

---

### Proposal F — Export endpoints: make caching controllable and observable
**Reasoning (observed):**
- Screenshot export appears cached/idempotent; may be stale after changes.
- PDF export regenerates each time (can be expensive and creates many files).

**Design:**
- Add `force` (default false) and `mode` (`cached|fresh`) parameters for both PDF and screenshot.
- Return metadata `{url, generatedAt, basedOnResumeUpdatedAt, cacheHit}`.

**Benefits:**
- Agents can guarantee freshness when needed (e.g., sending to a user).
- Reduced storage churn when freshness isn’t required.

---

### Proposal G — Add resume metadata patching and tag normalization
**Reasoning (observed):**
- No tool to rename a resume or update tags; duplicates allowed; case-sensitive matching.

**Design:**
- Add `resume.doc.patch({resume_id, name?, tags?, isPublic?, isLocked?})`.
- Normalize tags: trim, dedup, optional lowercase.

**Benefits:**
- Completes automation story (create → refine → publish).
- Reduces surprising tag filter behavior.

---

## Appendix — Selected Raw Test Transcripts & Observations

### A1) `doc.list` works with no args (despite signature implying required `tags`)
**Input**
```json
{}
```
**Output (success)**
```json
{
  "status": "success",
  "response": [
    {"id":"...","name":"...","tags":[...],"createdAt":"...","updatedAt":"..."}
  ]
}
```
**Why it matters:** displayed tool schema can mislead agents into always providing `tags:[]`.

---

### A2) `doc.create` accepts `basics` object (contradicting the visible `basics?: null`)
**Input**
```json
{"name":"MCP Eval - Create With Basics","tags":["mcp-eval","create"],"basics":{"name":"Should Fail"}}
```
**Output**
```json
{
  "status":"success",
  "response":{
    "resume_id":"019c49dc-3546-752b-9038-3946e7518f23",
    "basics":{"name":"Should Fail","label":null,...}
  }
}
```

---

### A3) Basics `location` must be a string (object rejected)
**Input**
```json
{
  "resume_id":"<id>",
  "payload":{"location":{"city":"San Francisco","region":"CA","countryCode":"US"}},
  "clear_fields":[]
}
```
**Output**
```json
{
  "status":"error",
  "error":{
    "httpStatus":400,
    "code":"VALIDATION_ERROR",
    "details":[{"field":"location","message":"Input should be a valid string"}]
  }
}
```

---

### A4) Work schema discovery via error → corrected payload
**Attempted (JSON Resume-like)**
```json
{"section":"work","items":[{"name":"Example","summary":"...","highlights":["..."]}]}
```
**Error**
- `summary` and `highlights` → `extra_forbidden`

**Corrected**
```json
{"section":"work","items":[{"name":"Example","description":"..."}]}
```

---

### A5) Wrapper-level validation failures have a different format
Calling `resume.doc.list` with wrong type:
```json
{"tags":"pytest","sort":"lastUpdatedAt"}
```
Resulted in a tool invocation failure (Pydantic), not a normal `{status:"error"}` envelope.

---

### A6) Screenshot export appears cached (same URL on repeated calls)
- `resume.export.screenshot({resume_id})` returned the same `.webp` URL on repeated calls.
- `resume.export.pdf({resume_id})` returned a new timestamped `.pdf` URL each call.

---

### A7) Discovered section schemas (empirical)
From `section.list` and successful creates/updates:

- **work:** `name, position, location, startDate, endDate, url, description`
- **education:** `institution, studyType, area, score, location, startDate, endDate, url, description`
- **projects:** `name, startDate, endDate, url, description`
- **skills:** `name, level, rating(number), keywords(string[])`
- **languages:** `language, fluency, level(number)`
- **interests:** `name, keywords(string[])`
- **awards:** `title, awarder, date, summary, url`
- **certificates:** `name, issuer, date, description, url`
- **publications:** `name, publisher, releaseDate, url, summary`
- **volunteer:** `organization, location, startDate, endDate, url, summary` (**no position**)
- **references:** `name, position, url, contact, reference`
- **profiles:** `network, username, url`

---

### A8) Date validation applies to `startDate/endDate`
Invalid update:
```json
{"section":"work","items":[{"id":"...","startDate":"Jan 2024"}]}
```
Error:
- `"Dates must be ISO8601-like strings: YYYY, YYYY-MM, or YYYY-MM-DD"`
