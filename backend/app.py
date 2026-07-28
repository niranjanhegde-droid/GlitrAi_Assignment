import logging
import os
import threading
import uuid

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from config import Config
from models import Job, db
from llm_service import build_generation_prompt
from image_service import generate_image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")


def _allowed_image(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_IMAGE_EXTENSIONS
    )


def _save_reference_image(file_storage):
    """Saves the uploaded product image to disk, returns its static URL path."""
    os.makedirs(Config.STATIC_UPLOADS_DIR, exist_ok=True)
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    filename = secure_filename(f"{uuid.uuid4()}.{ext}")
    filepath = os.path.join(Config.STATIC_UPLOADS_DIR, filename)
    file_storage.save(filepath)
    return f"/static/uploads/{filename}"


def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        db.create_all()

    register_routes(app)
    return app


def process_job(app, job_id):
    """
    Runs the actual generation work off the request thread so /generate
    can return immediately with a job id, and the frontend polls
    /jobs/:id for progress - a small stand-in for a real task queue
    (celery/rq) without needing extra infra for a take-home.
    """
    with app.app_context():
        job = Job.query.get(job_id)
        if not job:
            return

        try:
            job.status = "processing"
            db.session.commit()

            prompt = build_generation_prompt(job.product_name, job.description)
            job.generated_prompt = prompt
            db.session.commit()

            image_url = generate_image(
                job.id, job.product_name, prompt, job.reference_image_url
            )

            job.result_image_url = image_url
            job.status = "completed"
            db.session.commit()

        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)
            db.session.commit()


def register_routes(app):

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"}), 200

    @app.post("/generate")
    def generate():
        # The frontend always submits multipart/form-data (so it can
        # attach the product image); plain JSON is also accepted for
        # scripted/API-only calls that don't need an image.
        if request.content_type and "multipart/form-data" in request.content_type:
            product_name = (request.form.get("product_name") or "").strip()
            description = (request.form.get("description") or "").strip()
            image_file = request.files.get("product_image")
        else:
            data = request.get_json(silent=True) or {}
            product_name = (data.get("product_name") or "").strip()
            description = (data.get("description") or "").strip()
            image_file = None

        if not product_name or not description:
            return (
                jsonify({"error": "product_name and description are both required"}),
                400,
            )

        reference_image_url = None
        if image_file and image_file.filename:
            if not _allowed_image(image_file.filename):
                return (
                    jsonify(
                        {
                            "error": "product_image must be one of: "
                            + ", ".join(sorted(Config.ALLOWED_IMAGE_EXTENSIONS))
                        }
                    ),
                    400,
                )
            reference_image_url = _save_reference_image(image_file)

        job = Job(
            product_name=product_name,
            description=description,
            status="pending",
            reference_image_url=reference_image_url,
        )
        db.session.add(job)
        db.session.commit()

        thread = threading.Thread(
            target=process_job, args=(app, job.id), daemon=True
        )
        thread.start()

        return jsonify(job.to_dict()), 202

    @app.get("/jobs/<job_id>")
    def get_job(job_id):
        job = Job.query.get(job_id)
        if not job:
            return jsonify({"error": "job not found"}), 404
        return jsonify(job.to_dict()), 200

    @app.get("/jobs")
    def list_jobs():
        jobs = Job.query.order_by(Job.created_at.desc()).all()
        return jsonify([j.to_dict() for j in jobs]), 200

    # --- minimal frontend, served straight from the same Flask app so
    # there's only one thing to deploy/host ---
    @app.get("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/<path:filename>")
    def frontend_assets(filename):
        if os.path.exists(os.path.join(FRONTEND_DIR, filename)):
            return send_from_directory(FRONTEND_DIR, filename)
        return jsonify({"error": "not found"}), 404


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
