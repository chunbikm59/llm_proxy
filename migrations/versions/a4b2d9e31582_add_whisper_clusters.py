"""add whisper clusters

Revision ID: a4b2d9e31582
Revises: c3a1f8e20471
Create Date: 2026-04-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4b2d9e31582'
down_revision: Union[str, Sequence[str], None] = 'c3a1f8e20471'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'whisper_clusters',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.Text(), unique=True, nullable=False),
        sa.Column('executable_path', sa.Text(), nullable=False),
        sa.Column('model_path', sa.Text(), nullable=False),
        sa.Column('n_threads', sa.Integer(), nullable=True),
        sa.Column('n_processors', sa.Integer(), nullable=True),
        sa.Column('beam_size', sa.Integer(), nullable=True),
        sa.Column('best_of', sa.Integer(), nullable=True),
        sa.Column('audio_ctx', sa.Integer(), nullable=True),
        sa.Column('max_instances', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('is_default', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.Text(), nullable=False),
    )
    op.add_column(
        'whisper_transcription_jobs',
        sa.Column('cluster_name', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('whisper_transcription_jobs', 'cluster_name')
    op.drop_table('whisper_clusters')
