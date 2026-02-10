## Executive Summary

The `resume.basics.*` surface (GET/CREATE/UPDATE/DELETE) is small and generally agent-friendly for common “fill in resume header” tasks: it supports partial updates, supports clearing fields (via `null`, and—observed—also via empty strings), and returns the full `basics` object after mutations.

The main usability risks for automated agents (especially smaller/self-hosted models) are **semantic redundancy/confusion (`create` vs `update`)** and **inconsistent error handling**. Some failures return a tidy `{status:"error", error:"…"}` envelope, while others fail at the tool-wrapper layer with verbose schema/validation errors; additionally, missing/nonexistent resume IDs yield different styles (“Invalid UUID” vs raw “HTTP 404: {…}”). These inconsistencies make it harder for constrained agents to reliably recover and self-correct.

High-level recommendations: **collapse `create`+`update` into one patch-like method**, **standardize all errors into one structured envelope (including validation errors)**, **fix the schema optionality mismatch so small agents don’t “spray nulls”**, and **document/encode normalization rules (empty string → null, URL auto-prefix)**.

---

## Testing Protocol

**Date of testing:** Tuesday, February 10, 2026  
**Scope constraint:** Tested **`resume.basics.get/create/update/delete` only**, using `resume.doc.*` purely to (a) create disposable resumes and (b) clean up.

### Procedure overview (simple tests first)
1. **Happy path CRUD:** create empty resume → `basics.get` → `basics.update` partial → `basics.create` partial → `basics.delete` → `basics.get`.
2. **Partial update semantics:** update only one field; clear a field via `null`.
3. **Input validation & edge cases:**  
   - `payload:null` and missing payload  
   - `payload:{}` (empty object)  
   - invalid `resume_id` format  
   - nonexistent `resume_id` (UUID but not found)  
   - wrong types + unknown keys (tool-wrapper validation)
4. **Normalization tests:** empty string behavior and URL normalization (e.g., `example.com` → `https://example.com`).
5. **Cleanup:** delete created resumes via `resume.doc.delete`.

---

## API Complexity Analysis (esp. for small/self-hosted models)

### Surface area & data shapes
- **Required argument everywhere:** `resume_id` (UUID string).
- **Data model:** `basics` is a shallow object with **7 scalar fields**:  
  `name`, `label`, `email`, `phone`, `location`, `url`, `summary`
- **Mutation methods:** both `create` and `update` accept a `payload` object with any subset of those fields.

### Complexity hotspots
1. **Two “write” methods with identical observed semantics.**  
   Smaller models may waste turns choosing between `create` and `update` or incorrectly assume `create` will fail if basics already exist.
2. **Optionality + null semantics are easy to mis-handle.**  
   If a tool schema *looks* like every field is required (even if it isn’t), a small model might include all keys with `null`, unintentionally clearing data.
3. **Error handling is not uniform.**  
   Constrained models do best when every error has a consistent `{code, message, remediation}` structure. Here, some errors are concise, others are verbose wrapper validation dumps, and 404 errors are stringified dicts.
4. **Resume ID acquisition dependency (supporting).**  
   In real usage, an agent often must locate a resume ID; long `doc.list` outputs can exceed small-model context limits (not a basics endpoint problem per se, but directly affects ability to call basics endpoints).

---

## Observed Issues Table

| Issue ID | Reasoning / Analysis (Step-by-Step) | Description | Impact (esp. small/self-hosted models) | Recommended change |
|---|---|---|---|---|
| B1 | (1) Created a resume with empty basics. (2) Ran `basics.update({name:"A"})` → name became “A”. (3) Ran `basics.create({name:"B"})` → name became “B”. (4) No “already exists” error; behavior matches patch/merge. | `resume.basics.create` and `resume.basics.update` are **functionally redundant** (observed identical “patch” semantics). | **High**: small models may hesitate/loop deciding which to call; future divergence would break agents that learned “either works.” | **Remove one** (prefer a single `basics.patch`), or make semantics distinct & enforced (e.g., `create` fails if already initialized). |
| B2 | (1) `basics.get` with invalid UUID → clean `{status:"error", error:"Invalid resume_id …"}`. (2) Missing `resume_id` → tool call failed with wrapper validation dump. (3) Nonexistent UUID → `"HTTP 404: {…}"` string. | **Inconsistent error envelopes** across tool-level checks, wrapper/schema validation, and upstream HTTP errors. | **High**: small/self-hosted models often use simple pattern matching to recover; mixed formats cause brittle routing and failed retries. | Standardize *all* failures into one structured JSON error schema returned by the tool (including wrapper validation). Include `code`, `message`, `field`, `expected`, `received`, `retryable`. |
| B3 | (1) `basics.get("0000...")` → error string: `HTTP 404: {'defined': False, ...}`. (2) The dict is embedded as a **string**, not structured JSON. | 404 “Not Found” error is **stringified**, noisy, and not machine-friendly. | **Medium–High**: constrained agents may not reliably extract status/code; cannot branch cleanly (e.g., create-new vs abort). | Return `{"status":"error","code":"NOT_FOUND","httpStatus":404,"message":"Resume not found","resume_id":"…"}`. |
| B4 | (1) Sent wrong type `payload.name=123`. (2) Tool invocation failed with a long schema error (includes library-specific text and a URL). | Wrapper validation errors are **verbose** and include extraneous details. | **High**: small models can be derailed by long, non-actionable text; harder to map to a fix. | Catch/transform validation exceptions into compact field-level errors; omit library branding/links; include minimal actionable message. |
| B5 | (1) Schema suggests fields are `string|null`. (2) Partial payloads work (`{label:"Engineer"}`). (3) Small models might include all keys with `null` to be “safe,” unintentionally clearing values. | **Schema optionality mismatch** can induce accidental data loss (“null spraying”). | **High**: classic small-model failure mode. | Ensure schema marks fields as optional; explicitly define semantics: “omitted = unchanged; null/empty = clear”. Provide a `clearFields:[]` alternative to avoid null confusion. |
| B6 | (1) `basics.update(payload:{})` → `{status:"error", error:"No fields provided…"}`. (2) `basics.create(payload:{})` → same error text referencing update. | Empty payload errors are reasonable, but **messaging is confusing** (`create` path still says “update”). | **Low–Medium**: UX friction; can cause unnecessary retries. | Tailor error messages per operation OR treat empty payload as a no-op success (optionally with warning). |
| B7 | (1) Successful mutation returns only basics object. (2) To confirm broader resume metadata, needed `resume.doc.get`. | Success responses omit helpful metadata (`resume_id`, timestamps, changed fields). | **Medium**: extra calls increase cost; small models more likely to lose state across turns. | Include `resume_id` in all basics responses; optionally include `updatedAt` and `changedFields`. Offer `response_mode:"compact"` to minimize tokens. |
| B8 | (1) Set `url:"example.com"` → returned `"https://example.com"`. (2) Set `email:""` or `name:""` → returned `null`. (3) Set `"   "` (whitespace) → preserved. | Implicit **normalization rules** (empty string → null; URL auto-prefix) are helpful but undocumented/implicit. | **Medium**: agents may be surprised by transformations and mis-diagnose them as bugs. | Document normalization explicitly; optionally return `normalizations:[{field,from,to,rule}]` in debug mode. |
| B9 | (1) Set `email:"not an email"` → accepted. (2) URL gets normalization, but email/phone do not. | Inconsistent validation/normalization across fields. | **Low–Medium**: not strictly required, but inconsistent constraints reduce predictability. | Either validate email/phone consistently, or adopt a clear “no validation” policy for all fields with explicit opt-in validation. |

---

## Redesign Proposals

1. **Unify write operations into a single patch endpoint**
   - **Proposal:** Replace `resume.basics.create` + `resume.basics.update` with `resume.basics.patch`.
   - **Rationale:** Observed semantics are identical; one endpoint reduces agent branching and training burden.
   - **Benefit:** Smaller models avoid “which verb?” confusion and reduce retries.

2. **One canonical, structured error contract across every failure mode**
   - **Proposal:** Every failure (including missing args / wrong types / upstream 404) returns:
     ```json
     {
       "status": "error",
       "code": "VALIDATION_ERROR",
       "message": "payload.name must be a string",
       "details": [{"field":"payload.name","expected":"string","received":"int"}],
       "retryable": false
     }
     ```
   - **Rationale:** Agents currently must handle multiple error shapes.
   - **Benefit:** Deterministic recovery logic for constrained agents.

3. **Fix schema optionality to prevent accidental clearing**
   - **Proposal:** Ensure the published schema marks payload fields as truly optional; explicitly document:
     - omitted field = unchanged
     - `null` or `""` = clear
   - **Optional enhancement:** add `clearFields:["summary","url"]`.
   - **Benefit:** Prevents accidental data loss from “null spraying.”

4. **Expose normalization/validation policy explicitly**
   - **Proposal:** Add an optional parameter like `normalize:true|false` (default true) and document rules:
     - empty string → null for all basics fields (observed)
     - URL auto-prefix behavior (observed)
   - **Benefit:** Predictable transformations; agents can reason about diffs.

5. **Return lightweight metadata on success (configurable)**
   - **Proposal:** Include at minimum `resume_id` in every success response
   - **Benefit:** Fewer follow-up calls; easier tool chaining for small models.

---

## Appendix — Raw Test Transcripts (abridged but faithful)

### A1) Create empty resume → basics.get
```json
CALL resume.doc.create
{"name":"Basics API Blackbox - Simple Tests Feb10 2026","slug":"basics-api-blackbox-simple-tests-20260210","tags":["mcp-eval","basics","simple-tests","2026-02-10"],"with_sample_data":false}

RETURN
{"status":"success","response":{"resume_id":"019c4913-1964-7527-8739-4881c490539b","resume":{"sections":{"basics":{"name":null,"label":null,"email":null,"phone":null,"location":null,"url":null,"summary":null},"...":"..."}}}}