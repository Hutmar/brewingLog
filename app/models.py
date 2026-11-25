"""SQLAlchemy models; table and column names follow brauprotokoll.sql exactly.

Primary keys are assigned by the application through sequences, because the
DDL defines plain INTEGER PRIMARY KEY columns. Dialects without sequence
support (e.g. SQLite) fall back to their native integer key generation.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    Sequence,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Recipe(Base):
    __tablename__ = "recipe"
    __table_args__ = (UniqueConstraint("recipe_name"),)

    recipe_id: Mapped[int] = mapped_column(
        Integer, Sequence("recipe_recipe_id_seq"), primary_key=True
    )
    recipe_name: Mapped[str] = mapped_column(String(255))


class Ingredient(Base):
    __tablename__ = "ingredient"
    __table_args__ = (UniqueConstraint("ingredient_type", "name"),)

    ingredient_id: Mapped[int] = mapped_column(
        Integer, Sequence("ingredient_ingredient_id_seq"), primary_key=True
    )
    ingredient_type: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(100))
    stock: Mapped[Decimal | None] = mapped_column(
        Numeric(7, 2), server_default="0", default=Decimal("0")
    )
    unit: Mapped[str] = mapped_column(String(20), server_default="kg", default="kg")
    change_date: Mapped[date] = mapped_column(Date)

    attributes: Mapped[list["IngredientAttribute"]] = relationship(
        back_populates="ingredient", cascade="all, delete-orphan"
    )


class IngredientAttribute(Base):
    __tablename__ = "ingredient_attribute"

    ingredient_attribute_id: Mapped[int] = mapped_column(
        Integer, Sequence("ingredient_attribute_id_seq"), primary_key=True
    )
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredient.ingredient_id"))
    attribute_name: Mapped[str] = mapped_column(String(255))
    attribute_value: Mapped[str] = mapped_column(String(255))

    ingredient: Mapped[Ingredient] = relationship(back_populates="attributes")


class BrewingLog(Base):
    __tablename__ = "brewing_log"

    brewing_log_id: Mapped[int] = mapped_column(
        Integer, Sequence("brewing_log_brewing_log_id_seq"), primary_key=True
    )
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.recipe_id"))
    brewing_date: Mapped[date] = mapped_column(Date)
    plato_target: Mapped[Decimal] = mapped_column(Numeric(3, 1))
    plato_before_boiling: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    water_addition_boiling: Mapped[Decimal | None] = mapped_column(
        Numeric(2, 1), server_default="0", default=Decimal("0")
    )
    plato_after_boiling: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    plato_current: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    yeast: Mapped[int] = mapped_column(ForeignKey("ingredient.ingredient_id"))
    deviations: Mapped[str | None] = mapped_column(String(2000))
    alcohol_target: Mapped[Decimal] = mapped_column(Numeric(3, 2))
    alcohol_before_sec_fermentation: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    alcohol_after_sec_fermentation: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    temperature_fermentation: Mapped[Decimal] = mapped_column(Numeric(3, 1))
    volume_after_fermentation: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    water_addition_fermentation: Mapped[Decimal | None] = mapped_column(
        Numeric(2, 1), server_default="0", default=Decimal("0")
    )
    bottling_volume: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    bottling_date: Mapped[date | None] = mapped_column(Date)
    sugar_total: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    co2_target: Mapped[Decimal] = mapped_column(Numeric(2, 1))
    pressure_current: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    co2_current: Mapped[Decimal | None] = mapped_column(Numeric(2, 1))
    lagering_startdate: Mapped[date | None] = mapped_column(Date)

    recipe: Mapped[Recipe] = relationship()
    yeast_ingredient: Mapped[Ingredient] = relationship()
    ratings: Mapped[list["Rating"]] = relationship(
        back_populates="brewing_log", cascade="all, delete-orphan"
    )


class Rating(Base):
    __tablename__ = "rating"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 10"),)

    rating_id: Mapped[int] = mapped_column(
        Integer, Sequence("rating_rating_id_seq"), primary_key=True
    )
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    remark: Mapped[str | None] = mapped_column(String(500))
    brewing_log_id: Mapped[int] = mapped_column(ForeignKey("brewing_log.brewing_log_id"))

    brewing_log: Mapped[BrewingLog] = relationship(back_populates="ratings")
