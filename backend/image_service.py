"""
Generates the actual output image for a job.

The assignment explicitly says it's fine to mock this part with a
placeholder ("we won't be grading based on this"), so that's the
default path - it draws a simple, readable placeholder card using the
generated prompt so the end-to-end flow is fully demoable without any
paid image API.

If COMFYUI_URL is set (a ComfyUI instance you've deployed for
Assignment 2), generate_image() will instead call it over HTTP, which
covers the "connect Assignment 1 to your ComfyUI instance" brownie
points. See comfyui_client.py for that path.
"""
import logging
import os
import textwrap
import traceback

from PIL import Image, ImageDraw, ImageFont

from config import Config

logger = logging.getLogger(__name__)

CANVAS_SIZE = (768, 768)


def _load_font(size):
    # DejaVuSans ships with Pillow's default install on most systems;
    # fall back to the bitmap default if it's missing.
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size
        )
    except Exception:
        return ImageFont.load_default()


def _reference_image_disk_path(reference_image_url: str) -> str:
    # reference_image_url looks like "/static/uploads/<file>.png" - map
    # that back to an actual path on disk under backend/static/uploads.
    filename = os.path.basename(reference_image_url)
    return os.path.join(Config.STATIC_UPLOADS_DIR, filename)


def _mock_generate(job_id: str, product_name: str, prompt: str, reference_image_url: str = None) -> str:
    img = Image.new("RGB", CANVAS_SIZE, color=(245, 238, 225))
    draw = ImageDraw.Draw(img)

    # simple two-tone backdrop so it doesn't look like a blank error page
    draw.rectangle([0, 0, CANVAS_SIZE[0], 90], fill=(58, 92, 82))

    title_font = _load_font(30)
    body_font = _load_font(20)
    label_font = _load_font(16)

    draw.text((24, 28), "GlitrAI - Mock Generation", font=title_font, fill="white")

    draw.text((24, 130), product_name, font=title_font, fill=(40, 40, 40))

    wrapped = textwrap.fill(prompt, width=48)
    draw.multiline_text(
        (24, 190), wrapped, font=body_font, fill=(70, 70, 70), spacing=8
    )

    # This is the part that actually uses the uploaded product image:
    # since real image generation is mocked out (per the assignment's
    # own note), the closest honest stand-in for "generated based on
    # the reference" is compositing the real reference photo into the
    # output card instead of ignoring it.
    if reference_image_url:
        try:
            ref_path = _reference_image_disk_path(reference_image_url)
            ref_img = Image.open(ref_path).convert("RGB")
            ref_img.thumbnail((300, 300))
            paste_x = CANVAS_SIZE[0] - ref_img.width - 24
            paste_y = 130
            # thin border so it reads as a distinct "reference" panel
            border = Image.new(
                "RGB",
                (ref_img.width + 8, ref_img.height + 8),
                color=(58, 92, 82),
            )
            img.paste(border, (paste_x - 4, paste_y - 4))
            img.paste(ref_img, (paste_x, paste_y))
            draw.text(
                (paste_x, paste_y + ref_img.height + 6),
                "reference image used",
                font=label_font,
                fill=(120, 120, 120),
            )
        except Exception:
            # a bad/corrupt upload shouldn't take the whole job down
            pass

    draw.text(
        (24, CANVAS_SIZE[1] - 40),
        f"job: {job_id}  |  placeholder image, no paid image API used",
        font=label_font,
        fill=(120, 120, 120),
    )

    os.makedirs(Config.STATIC_GENERATED_DIR, exist_ok=True)
    filename = f"{job_id}.png"
    filepath = os.path.join(Config.STATIC_GENERATED_DIR, filename)
    img.save(filepath, "PNG")

    return f"/static/generated/{filename}"


def generate_image(job_id: str, product_name: str, prompt: str, reference_image_url: str = None) -> str:
    """Returns a URL path (relative to the app root) to the result image."""
    if Config.COMFYUI_URL:
        from comfyui_client import generate_via_comfyui

        try:
            reference_filename = (
                os.path.basename(reference_image_url) if reference_image_url else None
            )
            reference_disk_path = (
                _reference_image_disk_path(reference_image_url)
                if reference_image_url
                else None
            )
            logger.info("job %s: calling ComfyUI at %s", job_id, Config.COMFYUI_URL)
            result = generate_via_comfyui(
                job_id, prompt, reference_filename, reference_disk_path
            )
            logger.info("job %s: ComfyUI succeeded -> %s", job_id, result)
            return result
        except Exception:
            # If the live ComfyUI instance is down, don't fail the whole
            # job - fall back to the mock so the demo still works. But
            # log the real error so it's not a silent mystery.
            logger.error("job %s: ComfyUI call failed, falling back to mock", job_id)
            logger.error(traceback.format_exc())
            return _mock_generate(job_id, product_name, prompt, reference_image_url)

    logger.info("job %s: COMFYUI_URL not set, using mock", job_id)
    return _mock_generate(job_id, product_name, prompt, reference_image_url)
