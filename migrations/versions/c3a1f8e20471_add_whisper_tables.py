"""add whisper tables

Revision ID: c3a1f8e20471
Revises: b610b56a9879
Create Date: 2026-04-02 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a1f8e20471'
down_revision: Union[str, Sequence[str], None] = 'b610b56a9879'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'whisper_instances',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.Text(), unique=True, nullable=False),
        sa.Column('executable_path', sa.Text(), nullable=False),
        sa.Column('model_path', sa.Text(), nullable=False),
        sa.Column('host', sa.Text(), nullable=False, server_default='127.0.0.1'),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('n_threads', sa.Integer(), nullable=True),
        sa.Column('n_processors', sa.Integer(), nullable=True),
        sa.Column('beam_size', sa.Integer(), nullable=True),
        sa.Column('best_of', sa.Integer(), nullable=True),
        sa.Column('audio_ctx', sa.Integer(), nullable=True),
        sa.Column('auto_start', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('auto_restart', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_restart_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('startup_timeout', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('is_active', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.Text(), nullable=False),
    )

    op.create_table(
        'whisper_transcription_jobs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('instance_name', sa.Text(), nullable=True),
        sa.Column('filename', sa.Text(), nullable=False),
        sa.Column('language', sa.Text(), nullable=True),
        sa.Column('audio_duration_ms', sa.Integer(), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False, server_default='pending'),
        sa.Column('response_format', sa.Text(), nullable=False, server_default='json'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.Text(), nullable=False),
        sa.Column('completed_at', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('whisper_transcription_jobs')
    op.drop_table('whisper_instances')
