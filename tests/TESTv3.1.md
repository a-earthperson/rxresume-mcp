## Regression rerun (Feb 10, 2026) — results vs your prior report

I re-executed the same test *intent* as in the report (CRUD-ish flow, partial updates, clearing semantics, validation/error-shape probing, normalization), using the **currently exposed** tool surface.

### Important API surface change (breaking)
In the tool surface available **today (Feb 10, 2026)**, I **do not have** `resume.basics.create` or `resume.basics.update`. Instead, I have:

- `resume.basics.get`
- `resume.basics.patch`
- `resume.basics.delete` (but see regression below)

So I mapped your old test cases as:

- `basics.update` / `basics.create` ⇒ **`basics.patch`** (merge/patch semantics)
- `basics.delete` ⇒ **`basics.delete`** (expected “reset”), but it appears **broken** right now

This is a **breaking change** for any agents coded to call `create/update`.

---

## 1) Happy-path flow rerun (mapped to current endpoints)

### Steps I ran (with observed behavior)
1. **Create disposable resume**
   - `resume.doc.create(...)` → success, returned `resume_id = 019c4938-a9cc-73fe-adc2-02b7b9fe6dbf`.

2. **Get basics**
   - `resume.basics.get({resume_id})` → success  
   - **Change vs report:** response now includes `resume_id` alongside `response` basics object.

3. **Patch name=A**
   - `resume.basics.patch({resume_id, payload:{name:"A"}})` → success, `name:"A"`

4. **Patch name=B** (previously your “create vs update redundancy” check)
   - `resume.basics.patch({resume_id, payload:{name:"B"}})` → success, `name:"B"`
   - Confirms **patch/merge** semantics.

5. **Clear via null**
   - `resume.basics.patch({payload:{label:null}})` after setting label → success, label cleared to `null`

6. **Reset basics**
   - Expected: `resume.basics.delete({resume_id})` resets everything  
   - **Observed:** `resume.basics.delete` fails (details below).  
   - Workaround (works): `resume.basics.patch({payload:{}, clear_fields:[all fields]})`

7. **Delete resume**
   - `resume.doc.delete({resume_id})` → success

---

## 2) Validation & error-shape regression checks

### What I tested
- invalid `resume_id` format
- nonexistent UUID (404)
- missing `payload`
- `payload:null`
- `payload:{}`
- wrong types (e.g., `name: 123`)
- unknown keys (e.g., `payload:{unknown:"x"}`)

### What I observed (vs your prior report)
**Reasoning / steps**
- I intentionally triggered each failure mode using the same kinds of inputs as in your appendix/tests.
- I compared the *shape* of returned errors, since you previously saw multiple inconsistent formats (clean `{status:"error", error:"..."}` in some cases, wrapper dumps in others, stringified 404s).

**Result**
- **Most errors are now consistently structured** as:

```json
{
  "status": "error",
  "error": {
    "httpStatus": 400,
    "code": "VALIDATION_ERROR",
    "message": "...",
    "details": [...],
    "issues": [...],
    "retryable": false
  },
  "resume_id": "..."
}