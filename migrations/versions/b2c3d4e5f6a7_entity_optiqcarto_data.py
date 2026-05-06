"""Add optiqcarto_data to Entity

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('entities', sa.Column('optiqcarto_data', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('entities', 'optiqcarto_data')
