# Reactive Resume API Endpoints (MCP client usage)

Base URL: `DOMAIN/api/openapi`

All endpoints require the `x-api-key` header. `resume_id` values must be UUID
strings (the MCP client validates before calling the API).

## Endpoints used by the MCP client

## List all resumes
- **GET** `/resume/list`
- Query params:
  - `tags` (string[], optional; encoded as `tags[]`)
  - `sort` (string, optional; enum: `lastUpdatedAt` (desc) | `createdAt` (asc) | `name` (asc))
- Response: array of resume summaries (API-defined shape; MCP forwards JSON).

## Get resume by ID
- **GET** `/resume/{id}`
- Path params:
  - `id` (string, required; UUID)
- Response: full resume object including `data`.

## Get resume by username and slug
- **GET** `/resume/{username}/{slug}`
- Path params:
  - `username` (string, required)
  - `slug` (string, required)
- Response: resume object including `data`.

## Create a new resume
- **POST** `/resume/create`
- Body (JSON):
  - `name` (string, required)
  - `slug` (string, required)
  - `tags` (string[], required; can be empty array)
  - `withSampleData` (boolean, optional; default `false`)
- Response: created resume ID (string). MCP can optionally fetch the full resume.

## Update a resume
- **PUT** `/resume/{id}`
- Path params:
  - `id` (string, required; UUID)
- Body (JSON):
  - `name` (string, optional)
  - `slug` (string, optional)
  - `tags` (string[], optional)
  - `data` (object, optional; full resume data object)
- MCP behavior:
  - If `data` is provided, the MCP client fetches the current resume, deep-merges
    dictionaries, replaces arrays, validates the full merged data against the
    local JSON schema, then PUTs.
- Response: updated resume object (API-defined; MCP forwards JSON).

## Patch a resume
- **PATCH** `/resume/{id}`
- Path params:
  - `id` (string, required; UUID)
- Headers:
  - `Content-Type: application/json` (MCP uses JSON with an `id` wrapper)
- Body (JSON):
  - `{ "id": "<resume_id>", "patch": [ ... RFC 6902 ops ... ] }`
  - RxResume supports by-id paths for section items/custom sections.
  - MCP auto-injects ids for add ops that append to:
    `/data/sections/<section>/items/-`, `/data/customSections/-`,
    `/data/customSections/id/<custom_section_id>/items/-`,
    `/data/basics/customFields/-`.
- Response: updated resume object (same shape as GET /resume/{id}).

## Delete a resume
- **DELETE** `/resume/{id}`
- Path params:
  - `id` (string, required; UUID)
- Body (JSON): `{}` (MCP sends an empty JSON body)
- Response: may be empty (MCP returns `None` in the response payload).

## Export resume as PDF
- **GET** `/printer/resume/{id}/pdf`
- Response:
  - If the API returns bytes, MCP base64-encodes to
    `{ content_type, content_base64, size_bytes }`.
  - If the API returns JSON/text, MCP forwards it as-is.

## Get resume screenshot
- **GET** `/printer/resume/{id}/screenshot`
- Response: same behavior as PDF export (bytes -> base64; JSON/text forwarded).

## Other known endpoints (not wrapped by MCP tools)

These are present in the upstream API but are not used by this MCP client:

- **GET** `/resume/tags/list`
- **GET** `/resume/statistics/{id}`
- **POST** `/resume/import`
- **POST** `/resume/{id}/set-locked`
- **POST** `/resume/{id}/set-password`
- **POST** `/resume/{id}/remove-password`
- **POST** `/resume/{id}/duplicate`
