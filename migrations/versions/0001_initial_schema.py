"""Initial schema as defined by brauprotokoll.sql.

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _pk(name: str, seq: str) -> sa.Column:
    return sa.Column(name, sa.Integer, sa.Sequence(seq), primary_key=True)


SEQUENCES = (
    "recipe_recipe_id_seq",
    "ingredient_ingredient_id_seq",
    "ingredient_attribute_id_seq",
    "brewing_log_brewing_log_id_seq",
    "rating_rating_id_seq",
)


def _supports_sequences() -> bool:
    return op.get_bind().dialect.supports_sequences


def upgrade() -> None:
    # op.create_table does not create the sequences attached to its columns.
    if _supports_sequences():
        for name in SEQUENCES:
            op.execute(sa.schema.CreateSequence(sa.Sequence(name)))
    op.create_table(
        "recipe",
        _pk("recipe_id", "recipe_recipe_id_seq"),
        sa.Column("recipe_name", sa.String(255), nullable=False),
        sa.UniqueConstraint("recipe_name"),
    )
    op.create_table(
        "ingredient",
        _pk("ingredient_id", "ingredient_ingredient_id_seq"),
        sa.Column("ingredient_type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("stock", sa.Numeric(4, 2), server_default="0"),
        sa.Column("change_date", sa.Date, nullable=False),
        sa.UniqueConstraint("ingredient_type", "name"),
    )
    op.create_table(
        "ingredient_attribute",
        _pk("ingredient_attribute_id", "ingredient_attribute_id_seq"),
        sa.Column("ingredient_id", sa.Integer, sa.ForeignKey("ingredient.ingredient_id"), nullable=False),
        sa.Column("attribute_name", sa.String(255), nullable=False),
        sa.Column("attribute_datatype", sa.String(50), nullable=False),
        sa.Column("attribute_value", sa.String(255), nullable=False),
    )
    op.create_table(
        "brewing_log",
        _pk("brewing_log_id", "brewing_log_brewing_log_id_seq"),
        sa.Column("recipe_id", sa.Integer, sa.ForeignKey("recipe.recipe_id"), nullable=False),
        sa.Column("brewing_date", sa.Date, nullable=False),
        sa.Column("plato_target", sa.Numeric(3, 1), nullable=False),
        sa.Column("plato_before_boiling", sa.Numeric(3, 1)),
        sa.Column("water_addition_boiling", sa.Numeric(2, 1), server_default="0"),
        sa.Column("plato_after_boiling", sa.Numeric(3, 1)),
        sa.Column("plato_current", sa.Numeric(3, 1)),
        sa.Column("yeast", sa.Integer, sa.ForeignKey("ingredient.ingredient_id"), nullable=False),
        sa.Column("deviations", sa.String(2000)),
        sa.Column("alcohol_target", sa.Numeric(3, 2), nullable=False),
        sa.Column("alcohol_before_sec_fermentation", sa.Numeric(3, 2)),
        sa.Column("alcohol_after_sec_fermentation", sa.Numeric(3, 2)),
        sa.Column("temperature_fermentation", sa.Numeric(3, 1), nullable=False),
        sa.Column("volume_after_fermentation", sa.Numeric(3, 1)),
        sa.Column("water_addition_fermentation", sa.Numeric(2, 1), server_default="0"),
        sa.Column("bottling_volume", sa.Numeric(3, 1)),
        sa.Column("bottling_date", sa.Date),
        sa.Column("alcohol_current", sa.Numeric(3, 2)),
        sa.Column("sugar_total", sa.Numeric(4, 1)),
        sa.Column("co2_target", sa.Numeric(2, 1), nullable=False),
        sa.Column("pressure_current", sa.Numeric(2, 1)),
        sa.Column("co2_current", sa.Numeric(2, 1)),
        sa.Column("lagering_startdate", sa.Date),
    )
    op.create_table(
        "rating",
        _pk("rating_id", "rating_rating_id_seq"),
        sa.Column("rating", sa.SmallInteger),
        sa.Column("remark", sa.String(500)),
        sa.Column("brewing_log_id", sa.Integer, sa.ForeignKey("brewing_log.brewing_log_id"), nullable=False),
        sa.CheckConstraint("rating BETWEEN 1 AND 10"),
    )


def downgrade() -> None:
    for table in ("rating", "brewing_log", "ingredient_attribute", "ingredient", "recipe"):
        op.drop_table(table)
    if _supports_sequences():
        for name in SEQUENCES:
            op.execute(sa.schema.DropSequence(sa.Sequence(name)))
