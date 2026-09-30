"""Enable row-level security on every table (Postgres only).

On Supabase, tables in `public` are reachable through the REST API with the anon key. RLS with no
policies denies the anon and authenticated roles entirely; the API connects as the table owner,
which bypasses RLS. SQLite is untouched.

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _tables() -> list[str]:
    return sa.inspect(op.get_bind()).get_table_names(schema="public")


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for t in _tables():
        op.execute(f'ALTER TABLE public."{t}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON TABLE public."{t}" FROM anon, authenticated')


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for t in _tables():
        op.execute(f'ALTER TABLE public."{t}" DISABLE ROW LEVEL SECURITY')
