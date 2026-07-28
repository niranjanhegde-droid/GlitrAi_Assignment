# GlitrAI Mini Content Engine

A small service that turns a product name + description into an AI image
generation prompt, generates an image from it, and lets you track the job
and view the result. Built for the GlitrAI SDE Intern take-home
(Assignment 1), with a ComfyUI setup guide for Assignment 2 below.

## Why it's built this way

- **Flask + PostgreSQL** — matches the assignment's ask directly (postgres
  persistence), and keeps the whole thing to one small, easy-to-read
  codebase rather than pulling in a task-queue framework for something
  this size.
- **A background thread per job, not celery/rq** — `/generate` needs to
  return immediately with a job id while the actual work (LLM call +
  image generation) happens async. A real production system would use a
  proper queue; for a take-home, a daemon thread per job keeps the infra
  footprint at zero while still giving you real pending → processing →
  completed transitions.
- **LLM: Groq, with a template fallback** — Groq has a genuinely free
  tier and an OpenAI-compatible API, so `llm_service.py` is easy to swap
  for another provider. If no API key is set at all, it falls back to a
  rule-based prompt builder so the whole pipeline still runs end to end
  with zero signup.
- **Product image input** — `/generate` accepts an optional
  `product_image` upload (multipart form field). It's saved under
  `backend/static/uploads/` and its URL is stored on the job.
- **Image generation: mocked by default** — the assignment says this is
  fine and won't be graded. `image_service.py` draws a readable
  placeholder card (via Pillow) showing the product, the generated
  prompt, and — if one was uploaded — the actual reference image
  composited into the corner, so the output honestly reflects that a
  reference was used rather than ignoring it. If you plug in
  `COMFYUI_URL` (see Assignment 2 below), it routes through your live
  ComfyUI instance instead, uploading the reference image to ComfyUI
  first so it can actually be used in the img2img graph — that's the
  brownie-points integration.
- **Frontend: one plain HTML page + vanilla JS** — no build step, no
  framework, easy to serve straight from Flask so there's exactly one
  thing to deploy.

## Project structure

```
glitrai-content-engine/
├── backend/
│   ├── app.py                    # routes + job orchestration
│   ├── models.py                 # Job model (SQLAlchemy)
│   ├── config.py                 # env-driven config
│   ├── llm_service.py            # product info -> generation prompt
│   ├── image_service.py          # prompt -> image (mock by default)
│   ├── comfyui_client.py         # optional: routes generation through ComfyUI
│   ├── comfyui_workflow_api.json # placeholder - replace with your export
│   ├── requirements.txt
│   ├── Procfile                  # for gunicorn on Render/Heroku-style hosts
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── render.yaml                   # one-click-ish Render deploy blueprint
└── README.md
```

## API

| Method | Route          | Description                                      |
|--------|----------------|---------------------------------------------------|
| GET    | `/health`      | Basic health check → `{"status": "ok"}`           |
| POST   | `/generate`    | `multipart/form-data` with `product_name`, `description`, and an optional `product_image` file → creates a job, returns it immediately with `status: pending` (202). Plain JSON `{"product_name": "...", "description": "..."}` also works for API-only calls without an image. |
| GET    | `/jobs/:id`    | Returns the job's current status + result         |
| GET    | `/jobs`        | Lists all jobs, newest first (powers the frontend list) |

Job object:
```json
{
  "id": "uuid",
  "product_name": "...",
  "description": "...",
  "status": "pending | processing | completed | failed",
  "reference_image_url": "/static/uploads/<id>.jpg, or null if no image was uploaded",
  "generated_prompt": "... or null until processing starts",
  "result_image_url": "/static/generated/<id>.png, or null until completed",
  "error_message": "set only if status is failed",
  "created_at": "...",
  "updated_at": "..."
}
```

## Running it locally

Needs Python 3.10+.

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # then edit as needed
python app.py
```

Open **http://localhost:5000** — that's the frontend, served by the same
Flask app. No `DATABASE_URL` needed to just try it out locally: it falls
back to a local `sqlite` file automatically.

To use real Postgres locally instead:
```bash
# example with a local postgres running on default port
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/content_engine
```

To use a real LLM instead of the template fallback, grab a free key at
https://console.groq.com and set `GROQ_API_KEY` in `.env`.

## Deploying it publicly (Render, free tier)

The repo includes `render.yaml` so this is close to one click:

1. Push this repo to GitHub.
2. On [render.com](https://render.com), **New → Blueprint**, point it at
   the repo. Render reads `render.yaml` and provisions:
   - a free web service (`gunicorn app:app`)
   - a free Postgres database, wired to `DATABASE_URL` automatically
3. Set `GROQ_API_KEY` in the service's environment tab (optional but
   recommended so the demo shows a real LLM call, not just the fallback).
4. Deploy. First boot may take ~30–60s on the free tier (cold start).

No `render.yaml`? You can set the same thing up manually on Render,
Railway, or Fly.io: a Python web service with build command
`pip install -r backend/requirements.txt`, start command
`cd backend && gunicorn app:app --bind 0.0.0.0:$PORT`, plus a managed
Postgres add-on wired to `DATABASE_URL`.

## Assignment 2 — ComfyUI Img2Img + Upscaler on Colab

This part needs a live GPU session (Colab), so it isn't something I can
run for you inside this sandbox — but here's the exact path to set it up
and connect it to the service above.

**1. Get ComfyUI running on Colab**
- Use a ComfyUI Colab notebook (several public ones exist, e.g. search
  "ComfyUI Colab notebook" — most run a `git clone` of ComfyUI, install
  requirements, download a base checkpoint like SD1.5 or SDXL, then
  launch it with `cloudflared` or `localtunnel` so you get a public URL).
- Run all cells top to bottom. The last cell should print a public URL
  (a `*.trycloudflare.com` or `ngrok` link) — that's your `COMFYUI_URL`.

**2. Build the Img2Img + Upscaler workflow**
In the ComfyUI node editor:
- `LoadImage` → your product reference image
- `VAEEncode` → encodes that image into latent space (this is what
  makes it img2img instead of txt2img — it starts denoising from the
  reference latent instead of pure noise)
- `CLIPTextEncode` (positive) and `CLIPTextEncode` (negative) → your
  prompt and a standard negative prompt
- `KSampler` → set `denoise` below 1.0 (try 0.55–0.75) so it keeps the
  product's structure from the reference image instead of ignoring it
- `VAEDecode` → back to pixel space
- An **upscaler node** — either `LatentUpscale` before a second, lower-
  denoise `KSampler` pass (the common "hires fix" pattern), or an
  `UpscaleModelLoader` + `ImageUpscaleWithModel` (e.g. a 4x-ESRGAN
  model) applied to the decoded image
- `SaveImage` → your output node

**3. Save the workflow**
- Save the visual workflow as `.json` (File → Export, or the Save
  button) — this is the "saved workflow JSON" deliverable.
- Separately, enable **dev mode** in ComfyUI settings and use
  **"Save (API Format)"** — this is the machine-callable version. Drop
  that file in as `backend/comfyui_workflow_api.json`, replacing the
  placeholder.

**4. Connect it to Assignment 1 (brownie points)**
- Open the API-format JSON you just exported and note the actual node
  ids for your positive-prompt `CLIPTextEncode`, your `LoadImage`, and
  your `SaveImage` nodes.
- Update the three constants at the top of `backend/comfyui_client.py`
  (`POSITIVE_PROMPT_NODE`, `LOAD_IMAGE_NODE`, `SAVE_IMAGE_NODE`) to match.
- Set `COMFYUI_URL` to your Colab tunnel URL in the deployed service's
  env vars.
- With that set, `/generate` automatically routes image generation
  through your live ComfyUI instance instead of the mock (see
  `image_service.py` — it checks `Config.COMFYUI_URL` and switches
  paths). If ComfyUI is unreachable it falls back to the mock rather
  than failing the whole job.
- Heads up: Colab tunnels die when the notebook session ends, so this
  integration only works while your Colab is actively running — good
  enough for the demo video, not meant to be a permanent setup.

**Two distinct screenshots requirement:** run the same reference image +
prompt through the graph twice (different seed each time) and screenshot
both outputs — that's what the assignment is asking for.

## Submission checklist (from the assignment doc)

- [ ] Loom video, ≤5 min, one continuous take: show the app, walk
      through Assignment 1's code/model/API decisions, and talk through
      ComfyUI setup issues
- [ ] Public GitHub repo link (this codebase)
- [ ] Public hosted app link (Render URL from above)
- [ ] Two distinct ComfyUI screenshots (same reference + prompt, two
      generations)
- [ ] Saved ComfyUI workflow, `.json` format
- [ ] All links in one `.txt` file, in a shared Google Drive folder with
      the other deliverables
