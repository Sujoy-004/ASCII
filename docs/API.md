<!-- generated-by: gsd-doc-writer -->
# API Reference

The **RGB ASCII & Retro FX Studio API** is a high-performance FastAPI microservice designed for processing, assembling, and transcoding browser-recorded media streams into high-resolution MP4 video and animated GIF files.

---

## Authentication & Security

The API uses a layered token security model:

1. **Bot Mitigation (Turnstile)**:
   - Client requests to `/api/export/init` must provide a valid Cloudflare Turnstile token via header `X-Turnstile-Token` or JSON body `turnstileToken`.
   - Verified server-side against `https://challenges.cloudflare.com/turnstile/v0/siteverify`.
   <!-- VERIFY: Cloudflare Turnstile verification endpoint and secret key configuration in production dashboard. -->
2. **Job Ownership (`X-Job-Token`)**:
   - Initializing a job returns a cryptographic HMAC token tied to the `job_id`. All subsequent chunk uploads and status queries require the header:
     ```http
     X-Job-Token: <token>
     ```
3. **One-Time Download Token**:
   - Upon transcode completion, the status endpoint issues a short-lived, single-use download token passed as a query parameter:
     ```http
     GET /api/export/{job_id}/download?token=<download_token>
     ```

---

## Endpoints Overview

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| `GET` | `/health` | Container health check and server pre-warming ping. | None |
| `POST` | `/api/export/init` | Start an export session and reserve upload slot. | Turnstile |
| `POST` | `/api/export/{job_id}/chunk` | Stream sequential WebM recording chunk. | `X-Job-Token` |
| `POST` | `/api/export/{job_id}/source-audio` | Upload original source audio track for muxing. | `X-Job-Token` |
| `POST` | `/api/export/{job_id}/finalize` | Trigger asynchronous FFmpeg transcode worker. | `X-Job-Token` |
| `GET` | `/api/export/{job_id}/status` | Poll job state and transcoding progress percentage. | `X-Job-Token` |
| `POST` | `/api/export/{job_id}/cancel` | Abort processing and immediately clean up disk space. | `X-Job-Token` |
| `GET` | `/api/export/{job_id}/download` | Stream the finished MP4 or GIF artifact to the client. | Download Token |
| `POST` | `/api/export/video` | Direct single-request multipart video transcode. | Turnstile |

---

## Request & Response Formats

### 1. Health Check
`GET /health`

**Response (`200 OK`):**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "timestamp": 1731940000.123
}
```

### 2. Initialize Export Session
`POST /api/export/init`

**Request Body (`application/json`):**
```json
{
  "format": "mp4",
  "duration": 15.5,
  "fps": 30,
  "width": 1280,
  "height": 720,
  "hasAudio": true,
  "turnstileToken": "0.xxxxxx..."
}
```

**Response (`200 OK`):**
```json
{
  "jobId": "exp_abc123456789",
  "token": "hmac_signature_token...",
  "maxChunkSize": 5242880,
  "status": "initialized"
}
```

### 3. Upload Media Chunk
`POST /api/export/{job_id}/chunk?index=0&total=3`

**Request:** `multipart/form-data` with `file` binary chunk (`<= 5 MB`).

**Response (`200 OK`):**
```json
{
  "status": "chunk_received",
  "index": 0,
  "receivedBytes": 2097152
}
```

### 4. Trigger Final Transcode
`POST /api/export/{job_id}/finalize`

**Response (`200 OK`):**
```json
{
  "jobId": "exp_abc123456789",
  "status": "queued"
}
```

### 5. Poll Job Status
`GET /api/export/{job_id}/status`

**Response (`200 OK` - In Progress):**
```json
{
  "jobId": "exp_abc123456789",
  "status": "processing",
  "progress": 65,
  "format": "mp4"
}
```

**Response (`200 OK` - Completed):**
```json
{
  "jobId": "exp_abc123456789",
  "status": "completed",
  "progress": 100,
  "format": "mp4",
  "downloadToken": "dl_tok_987654321",
  "downloadUrl": "/api/export/exp_abc123456789/download?token=dl_tok_987654321"
}
```

---

## Error Handling & Status Codes

Standard API error envelopes:

```json
{
  "error": "server_busy",
  "message": "Transcode server is currently processing another export job.",
  "retry_after": 30
}
```

| HTTP Status | Meaning | Reason |
|-------------|---------|--------|
| `400 Bad Request` | Invalid parameters | Chunk exceeds 5MB or media duration exceeds limits (60s video / 15s GIF). |
| `401 Unauthorized` | Invalid authentication | Missing or tampered `X-Job-Token` or invalid Turnstile token. |
| `404 Not Found` | Unknown job ID | Job expired or cleaned up by storage janitor. |
| `429 Too Many Requests` | Rate limit exceeded | IP exceeded burst limit (e.g., > 5 init requests/min). |
| `503 Service Unavailable` | Server Concurrency Lock | Another active export job is currently occupying the container's CPU. Client should inspect `Retry-After: 30` header. |

---

## Rate Limits & Resource Bounds

Configured via SlowAPI and in-memory semaphores:

- **Health check**: `30 requests / minute` per client IP.
- **Job initialization**: `5 requests / minute` per client IP.
- **Finalize transcode**: `5 requests / minute` per client IP.
- **Concurrency limit**: Exactly `1` concurrent FFmpeg process per free-tier container instance.
