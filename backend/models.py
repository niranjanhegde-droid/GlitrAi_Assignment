import uuid
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def _uuid():
    return str(uuid.uuid4())


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    product_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)

    # pending -> processing -> completed | failed
    status = db.Column(db.String(20), nullable=False, default="pending")

    reference_image_url = db.Column(db.String(500), nullable=True)
    generated_prompt = db.Column(db.Text, nullable=True)
    result_image_url = db.Column(db.String(500), nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "product_name": self.product_name,
            "description": self.description,
            "status": self.status,
            "reference_image_url": self.reference_image_url,
            "generated_prompt": self.generated_prompt,
            "result_image_url": self.result_image_url,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
