"""Stock unit, wider stock/pressure columns, removal of unused columns.

- ingredient.unit (varchar(20), default 'kg') is added and ingredient.stock
  is widened to numeric(7,2) so that gram values fit.
- ingredient_attribute.attribute_datatype is dropped.
- brewing_log.alcohol_current is dropped.
- brewing_log.pressure_current becomes numeric(3,2).

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


# batch_alter_table issues plain ALTER statements on PostgreSQL and rebuilds
# the table on SQLite, which cannot alter or drop columns in place.
def upgrade() -> None:
    with op.batch_alter_table("ingredient") as batch:
        batch.add_column(sa.Column("unit", sa.String(20), nullable=False, server_default="kg"))
        batch.alter_column(
            "stock",
            existing_type=sa.Numeric(4, 2),
            type_=sa.Numeric(7, 2),
            existing_server_default="0",
        )
    with op.batch_alter_table("ingredient_attribute") as batch:
        batch.drop_column("attribute_datatype")
    with op.batch_alter_table("brewing_log") as batch:
        batch.drop_column("alcohol_current")
        batch.alter_column(
            "pressure_current", existing_type=sa.Numeric(2, 1), type_=sa.Numeric(3, 2)
        )


def downgrade() -> None:
    with op.batch_alter_table("brewing_log") as batch:
        batch.alter_column(
            "pressure_current", existing_type=sa.Numeric(3, 2), type_=sa.Numeric(2, 1)
        )
        batch.add_column(sa.Column("alcohol_current", sa.Numeric(3, 2)))
    with op.batch_alter_table("ingredient_attribute") as batch:
        batch.add_column(
            sa.Column("attribute_datatype", sa.String(50), nullable=False, server_default="text")
        )
    with op.batch_alter_table("ingredient") as batch:
        batch.alter_column(
            "stock",
            existing_type=sa.Numeric(7, 2),
            type_=sa.Numeric(4, 2),
            existing_server_default="0",
        )
        batch.drop_column("unit")
