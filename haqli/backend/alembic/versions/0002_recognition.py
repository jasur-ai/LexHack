"""Add Recognition Engine v1.0 columns & expiration indexes.

Revision ID: 0002_recognition
Revises: 0001_initial
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_recognition"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("recognition_jobs", sa.Column("result_enc", sa.Text(), nullable=True))
    op.add_column("recognition_jobs", sa.Column("file_id", sa.String(length=36), nullable=True))
    op.add_column(
        "recognition_jobs",
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_recog_expires_at", "recognition_jobs", ["expires_at"])

    op.add_column("uploaded_files", sa.Column("attached_case_id", sa.String(length=36), nullable=True))
    op.create_index("ix_uploaded_purge_at", "uploaded_files", ["purge_at"])


def downgrade() -> None:
    op.drop_index("ix_uploaded_purge_at", table_name="uploaded_files")
    op.drop_column("uploaded_files", "attached_case_id")

    op.drop_index("ix_recog_expires_at", table_name="recognition_jobs")
    op.drop_column("recognition_jobs", "confirmed")
    op.drop_column("recognition_jobs", "file_id")
    op.drop_column("recognition_jobs", "result_enc")
