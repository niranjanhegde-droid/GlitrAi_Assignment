"""
Talks to a running ComfyUI instance over its HTTP API so this service
can call the Assignment-2 workflow directly (the "brownie points"
part of the assignment).

ComfyUI itself isn't included here - you still need to stand it up on
Colab (or wherever) and export its workflow as API-format JSON (in the
ComfyUI menu: enable dev mode, then "Save (API Format)"). Drop that
export in backend/comfyui_workflow_api.json and point COMFYUI_URL at
your public ComfyUI URL (Colab's ngrok/cloudflare tunnel link works).

This is intentionally left as a working skeleton rather than something
I can fully guarantee end-to-end, since it depends entirely on your
node IDs from your saved workflow (see the NODE ID NOTE below).
"""
import json
import os
import time
import uuid

import requests

from config import Config

WORKFLOW_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "comfyui_workflow_api.json"
)

# NODE ID NOTE: these are the *typical* node titles in a default
# img2img + upscaler ComfyUI graph. Open your exported JSON and check
# the actual ids/titles - update the three constants below to match
# your workflow before this will work against your graph.
POSITIVE_PROMPT_NODE = "11"  # CLIPTextEncode (positive)
LOAD_IMAGE_NODE = "14"       # LoadImage (reference/product image)
SAVE_IMAGE_NODE = "10"       # SaveImageAdvanced / output node


def _load_workflow_template() -> dict:
    with open(WORKFLOW_PATH, "r") as f:
        return json.load(f)


def _upload_reference_image(local_path: str) -> str:
    """
    ComfyUI's LoadImage node reads from ComfyUI's own input folder, not
    an arbitrary URL - so the reference image has to be uploaded to the
    ComfyUI instance first via its /upload/image endpoint. Returns the
    filename ComfyUI stored it under, which is what LoadImage expects.
    """
    with open(local_path, "rb") as f:
        files = {"image": (os.path.basename(local_path), f)}
        resp = requests.post(
            f"{Config.COMFYUI_URL}/upload/image", files=files, timeout=30
        )
    resp.raise_for_status()
    return resp.json()["name"]


def generate_via_comfyui(
    job_id: str,
    prompt: str,
    reference_image_name: str = None,
    reference_image_disk_path: str = None,
) -> str:
    workflow = _load_workflow_template()

    if POSITIVE_PROMPT_NODE in workflow:
        workflow[POSITIVE_PROMPT_NODE]["inputs"]["text"] = prompt

    if reference_image_disk_path and LOAD_IMAGE_NODE in workflow:
        uploaded_name = _upload_reference_image(reference_image_disk_path)
        workflow[LOAD_IMAGE_NODE]["inputs"]["image"] = uploaded_name
    elif reference_image_name and LOAD_IMAGE_NODE in workflow:
        workflow[LOAD_IMAGE_NODE]["inputs"]["image"] = reference_image_name

    client_id = str(uuid.uuid4())
    queue_resp = requests.post(
        f"{Config.COMFYUI_URL}/prompt",
        json={"prompt": workflow, "client_id": client_id},
        timeout=30,
    )
    queue_resp.raise_for_status()
    prompt_id = queue_resp.json()["prompt_id"]

    # Poll history until ComfyUI reports this prompt as finished.
    # A real deployment would use the websocket endpoint instead of
    # polling, but polling is simpler to reason about for a take-home.
    for _ in range(60):
        time.sleep(2)
        hist_resp = requests.get(
            f"{Config.COMFYUI_URL}/history/{prompt_id}", timeout=15
        )
        hist_resp.raise_for_status()
        history = hist_resp.json()
        if prompt_id in history:
            outputs = history[prompt_id]["outputs"]
            node_output = outputs.get(SAVE_IMAGE_NODE)
            if node_output and "images" in node_output:
                image_info = node_output["images"][0]
                view_url = (
                    f"{Config.COMFYUI_URL}/view?filename={image_info['filename']}"
                    f"&subfolder={image_info.get('subfolder', '')}"
                    f"&type={image_info.get('type', 'output')}"
                )

                # Don't hand the raw ngrok URL back to the browser: ngrok's
                # free tier serves an HTML "you're about to visit..."
                # interstitial to direct browser/img requests unless a
                # special header is sent, which breaks <img src=...>.
                # Download the bytes here (server-to-server, no
                # interstitial issue) and save locally instead, so the
                # frontend just loads a normal /static/generated/ URL -
                # the same pattern the mock path already uses.
                img_resp = requests.get(
                    view_url,
                    headers={"ngrok-skip-browser-warning": "true"},
                    timeout=60,
                )
                img_resp.raise_for_status()

                os.makedirs(Config.STATIC_GENERATED_DIR, exist_ok=True)
                ext = os.path.splitext(image_info["filename"])[1] or ".png"
                filename = f"{job_id}{ext}"
                filepath = os.path.join(Config.STATIC_GENERATED_DIR, filename)
                with open(filepath, "wb") as f:
                    f.write(img_resp.content)

                return f"/static/generated/{filename}"

    raise TimeoutError("ComfyUI job did not complete in time")
