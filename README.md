# GlitrAI Mini Content Engine

**Live demo:** [comfy-ui-model.onrender.com](https://comfy-ui-model.onrender.com)

A small service that turns a product name, description, and reference image
into an AI-generated lifestyle product photo — built for the GlitrAI SDE
Intern take-home. Submit a product, watch the job move through
`pending → processing → completed`, and view the result. Assignment 2's
ComfyUI Img2Img + Upscaler workflow is documented further down, along with
how it's wired into this service.

---

## What it does

1. You submit a product name, a short description, and an optional
   reference photo.
2. An LLM turns that into a detailed image-generation prompt.
3. That prompt (plus the reference image) is sent to an image generation
   backend to produce the final creative.
4. The job's status and result are trackable in real time from the same
   page — no refresh needed, it polls automatically.

---

## Architecture & design decisions

- **Flask + PostgreSQL** — matches the assignment's persistence
  requirement directly, kept in one small, readable codebase rather than
  reaching for a heavier framework than the problem needs. Falls back to
  a local SQLite file automatically when no `DATABASE_URL` is set, so the
  project runs with zero setup for local development or review.
- **Background thread per job** — `/generate` returns immediately with a
  job id while the actual work (LLM call + image generation) runs
  asynchronously. A larger production system would use a proper task
  queue (Celery/RQ); for a service this size, a daemon thread per job
  gives real `pending → processing → completed` transitions without
  extra infrastructure.
- **LLM prompt generation via Groq** — Groq offers a genuinely free tier
  with an OpenAI-compatible API, making it easy to swap providers later.
  If no API key is configured, the service falls back to a rule-based
  prompt builder automatically, so the full pipeline still runs end to
  end without requiring anyone to sign up for anything just to try it.
- **Image generation, two backends** — by default this runs through a
  placeholder generator (explicitly permitted by the assignment brief).
  When a live ComfyUI instance is available (see Assignment 2 below),
  the same endpoint routes generation through it instead — uploading the
  reference image, running it through an Img2Img + upscaler workflow,
  and returning the real generated result. If the ComfyUI instance is
  ever unreachable, the service degrades gracefully back to the
  placeholder rather than failing the request.
- **Plain HTML/CSS/vanilla JS frontend** — no build step, served
  directly by Flask, so there's exactly one thing to deploy.

---

## Project structure

```
glitrai-content-engine/
├── backend/
│   ├── app.py                    # routes + job orchestration
│   ├── models.py                 # Job model (SQLAlchemy)
│   ├── config.py                 # env-driven configuration
│   ├── llm_service.py            # product info -> generation prompt
│   ├── image_service.py          # prompt -> image (placeholder or ComfyUI)
│   ├── comfyui_client.py         # routes generation through a live ComfyUI instance
│   ├── comfyui_workflow_api.json # exported ComfyUI workflow (API format)
│   ├── requirements.txt
│   ├── Procfile
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── render.yaml                   # Render deployment blueprint
└── README.md
```

---

## API

| Method | Route         | Description |
|--------|---------------|--------------|
| GET    | `/health`     | Health check → `{"status": "ok"}` |
| POST   | `/generate`   | `multipart/form-data` with `product_name`, `description`, and an optional `product_image` file. Creates a job and returns it immediately with `status: pending` (202). |
| GET    | `/jobs/:id`   | Returns a single job's current status and result |
| GET    | `/jobs`       | Lists all jobs, newest first |

**Job object:**
```json
{
  "id": "uuid",
  "product_name": "...",
  "description": "...",
  "status": "pending | processing | completed | failed",
  "reference_image_url": "/static/uploads/<id>.jpg, or null",
  "generated_prompt": "... or null until processing starts",
  "result_image_url": "/static/generated/<id>.png, or null until completed",
  "error_message": "set only if status is failed",
  "created_at": "...",
  "updated_at": "..."
}
```

---

## Running it locally

Requires Python 3.10+.

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # edit as needed
python app.py
```

Open **http://localhost:5000**. No `DATABASE_URL` is required to try it
out — it falls back to a local SQLite file automatically.

To use a real LLM instead of the template fallback, add a free key from
[console.groq.com](https://console.groq.com) as `GROQ_API_KEY` in `.env`.

---

## Deployment

Deployed on **Render** (free tier), using the included `render.yaml`
blueprint — provisions a web service plus a managed Postgres database,
with `DATABASE_URL` wired automatically.

**Live app:** [comfy-ui-model.onrender.com](https://comfy-ui-model.onrender.com)

Note: Render's free tier spins services down after periods of
inactivity, so the first request after a while may take 30–60 seconds
to respond while it wakes back up.

---

## Assignment 2 — ComfyUI Img2Img + Upscaler

Built and run on Google Colab's free GPU tier.

**Workflow graph:**
`Load Checkpoint` → `CLIP Text Encode` (positive/negative) →
`Load Image` → `VAE Encode` → `KSampler` (`latent_image` sourced from
the encoded reference — this is what makes the workflow Img2Img rather
than text-to-image) → `VAE Decode` → `Upscale Image (using Model)`
(4x-UltraSharp) → `Save Image`.

Denoise strength is tuned to preserve the reference image's composition
while letting the prompt drive styling, lighting, and detail — a value
near 1.0 effectively discards the reference; something in the 0.4–0.6
range keeps it recognizable while still letting the model meaningfully
restyle it.

**Deliverables included in this submission:**
- Saved workflow, `.json` format (UI export)
- Two screenshots of the workflow producing distinct outputs from the
  same reference image and prompt (different seeds)

**Connected to Assignment 1 (brownie points):** `comfyui_client.py`
uploads the reference image to the ComfyUI instance, injects the
generated prompt into the exported API-format workflow, queues the job,
polls for completion, and downloads the finished, upscaled image back
into this service — visible live in the demo video. Since the ComfyUI
instance runs on a Colab session, that specific integration is only
reachable while the session is active; outside of that window the
service automatically falls back to the placeholder generator rather
than failing, so the hosted app itself remains fully functional at all
times.

---

## Submission

- Loom video walkthrough (app demo, code walkthrough, ComfyUI setup)
- This repository
- Live app: [comfy-ui-model.onrender.com](https://comfy-ui-model.onrender.com)
- ComfyUI workflow JSON + two generation screenshots
