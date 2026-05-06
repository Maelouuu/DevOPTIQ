"""Add svg_content and vsdx_filename to Entity

Revision ID: a1b2c3d4e5f6
Revises: 4fe1f56bda52
Create Date: 2026-03-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '4fe1f56bda52'
branch_labels = None
depends_on = None


def upgrade():
    # op.add_column = ALTER TABLE ADD COLUMN : instantané sur PostgreSQL (pas de rebuild table)
    op.add_column('entities', sa.Column('svg_content', sa.Text(), nullable=True))
    op.add_column('entities', sa.Column('vsdx_filename', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('entities', 'svg_content')
    op.drop_column('entities', 'vsdx_filename')
