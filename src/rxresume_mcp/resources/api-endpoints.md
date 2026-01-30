# Reactive Resume API Endpoints (Resume)

Base URL: `DOMAIN/api/openapi`

All endpoints require `x-api-key` header.

## List all resume tags
- **GET** `/resume/tags/list`
- Response: array of strings (tags)

## Get resume statistics
- **GET** `/resume/statistics/{id}`
- Path params:
  - `id` (string, required)
- Response: `isPublic`, `views`, `downloads`, `lastViewedAt`, `lastDownloadedAt`

## List all resumes
- **GET** `/resume/list`
- Query params:
  - `tags` (string[], optional; encoded as `tags[]`)
  - `sort` (string, optional; default: `lastUpdatedAt`; enum options not exposed in docs)
- Response: array of resume summaries (id, name, slug, tags, isPublic, isLocked, createdAt, updatedAt)

## Get resume by ID
- **GET** `/resume/{id}`
- Path params:
  - `id` (string, required)
- Response: full resume object including `data`

## Create a new resume
- **POST** `/resume/create`
- Body (JSON):
  - `name` (string, required)
  - `slug` (string, required)
  - `tags` (string[], required; can be empty array)
  - `withSampleData` (boolean, optional; default `false`)
- Response: created resume ID (string)

## Import a resume
- **POST** `/resume/import`
- Body (JSON):
  - `data` (object, required; see resume schema)
- Response: imported resume ID (string)

## Update a resume
- **PUT** `/resume/{id}`
- Path params:
  - `id` (string, required)
- Body (JSON):
  - `name` (string, optional)
  - `slug` (string, optional)
  - `tags` (string[], optional)
  - `data` (object, optional; full resume data object)
  - `isPublic` (boolean, optional; not used by MVP script)
- Response: updated resume object (type not fully specified in docs)

## Delete a resume
- **DELETE** `/resume/{id}`
- Path params:
  - `id` (string, required)
- Response: unspecified

## Get resume by username and slug
- **GET** `/resume/{username}/{slug}`
- Path params:
  - `username` (string, required)
  - `slug` (string, required)
- Response: resume object including `data`

## Set resume locked status
- **POST** `/resume/{id}/set-locked`
- Body (JSON):
  - `isLocked` (boolean, required)
- Response: unspecified

## Set password on a resume
- **POST** `/resume/{id}/set-password`
- Body (JSON):
  - `password` (string, required; length 6-64)
- Response: unspecified

## Remove password from a resume
- **POST** `/resume/{id}/remove-password`
- Response: unspecified

## Duplicate a resume
- **POST** `/resume/{id}/duplicate`
- Body (JSON, optional):
  - `name` (string, optional)
  - `slug` (string, optional)
  - `tags` (string[], optional)
- Response: duplicated resume ID (string)

## Export resume as PDF
- **GET** `/printer/resume/{id}/pdf`
- Response: `{ "url": "<string>" }`

## Get resume screenshot
- **GET** `/printer/resume/{id}/screenshot`
- Response: `{ "url": "<string>" }`
