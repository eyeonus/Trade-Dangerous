# tradedangerous/db/orm_models.py
from __future__ import annotations

from sqlalchemy import (
    MetaData, ForeignKey, Integer, BigInteger, String, CHAR, Enum, Index, UniqueConstraint, text
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing import Optional
from sqlalchemy.dialects.mysql import DATETIME as MySQLDateTime

# ---------- Naming & Base ----------

naming_convention = {
    "ix": "ix_%(table_name)s__%(column_0_N_name)s",
    "uq": "uq_%(table_name)s__%(column_0_N_name)s",
    "ck": "ck_%(table_name)s__%(constraint_name)s",
    "fk": "fk_%(table_name)s__%(column_0_N_name)s__%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=naming_convention)

class Base(DeclarativeBase):
    metadata = metadata

# ---------- Enums ----------

TriState = Enum("Y", "N", "?", name="tri_state", native_enum=True)
PadSize  = Enum("S", "M", "L", "?", name="pad_size", native_enum=True)

# ---------- Core Domain ----------

class Added(Base):
    __tablename__ = "Added"
    added_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)

    # Relationships
    systems: Mapped[list["System"]] = relationship(back_populates="added")


class System(Base):
    __tablename__ = "System"
    system_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    pos_x: Mapped[float] = mapped_column(nullable=False)
    pos_y: Mapped[float] = mapped_column(nullable=False)
    pos_z: Mapped[float] = mapped_column(nullable=False)
    added_id: Mapped[int | None] = mapped_column(
        ForeignKey("Added.added_id", onupdate="CASCADE", ondelete="CASCADE")
    )
    modified: Mapped[str] = mapped_column(
        MySQLDateTime(fsp=6),
        server_default=text("CURRENT_TIMESTAMP(6)"),
        onupdate=text("CURRENT_TIMESTAMP(6)"),
        nullable=False,
    )

    # Relationships
    added: Mapped[Optional["Added"]] = relationship(back_populates="systems")
    stations: Mapped[list["Station"]] = relationship(back_populates="system", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_system_by_pos", "pos_x", "pos_y", "pos_z", "system_id"),
        Index("idx_system_by_name", "name"),
    )


class Station(Base):
    __tablename__ = "Station"
    station_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    system_id: Mapped[int] = mapped_column(ForeignKey("System.system_id", ondelete="CASCADE"), nullable=False)
    ls_from_star: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    blackmarket: Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))
    max_pad_size: Mapped[str] = mapped_column(PadSize,  nullable=False, server_default=text("'?'"))
    market:   Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))
    shipyard: Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))
    outfitting: Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))
    rearm:    Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))
    refuel:   Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))
    repair:   Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))
    planetary:Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))

    type_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    modified: Mapped[str] = mapped_column(
        MySQLDateTime(fsp=6),
        server_default=text("CURRENT_TIMESTAMP(6)"),
        onupdate=text("CURRENT_TIMESTAMP(6)"),
        nullable=False,
    )

    # Relationships
    system: Mapped["System"] = relationship(back_populates="stations")
    items: Mapped[list["StationItem"]] = relationship(back_populates="station", cascade="all, delete-orphan")
    ship_vendors: Mapped[list["ShipVendor"]] = relationship(back_populates="station", cascade="all, delete-orphan")
    upgrade_vendors: Mapped[list["UpgradeVendor"]] = relationship(back_populates="station", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_station_by_system", "system_id"),
        Index("idx_station_by_name", "name"),
        # Optional (enable once data validated):
        # UniqueConstraint("system_id", "name", name="uq_station_sys_name"),
    )


class Category(Base):
    __tablename__ = "Category"
    category_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)

    # Relationships
    items: Mapped[list["Item"]] = relationship(back_populates="category")

    __table_args__ = (Index("idx_category_by_name", "name"),)


class Item(Base):
    __tablename__ = "Item"
    item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("Category.category_id", ondelete="CASCADE"), nullable=False)
    ui_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    avg_price: Mapped[int | None] = mapped_column(Integer)   # TODO: verify presence/usage in legacy
    fdev_id: Mapped[int | None] = mapped_column(Integer)

    # Relationships
    category: Mapped["Category"] = relationship(back_populates="items")
    stations: Mapped[list["StationItem"]] = relationship(back_populates="item", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_item_by_fdevid", "fdev_id"),
        Index("idx_item_by_category", "category_id"),
    )


class StationItem(Base):
    __tablename__ = "StationItem"
    station_id: Mapped[int] = mapped_column(
        ForeignKey("Station.station_id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("Item.item_id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True
    )
    demand_price: Mapped[int] = mapped_column(Integer, nullable=False)
    demand_units: Mapped[int] = mapped_column(Integer, nullable=False)
    demand_level: Mapped[int] = mapped_column(Integer, nullable=False)
    supply_price: Mapped[int] = mapped_column(Integer, nullable=False)
    supply_units: Mapped[int] = mapped_column(Integer, nullable=False)
    supply_level: Mapped[int] = mapped_column(Integer, nullable=False)
    modified: Mapped[str] = mapped_column(
        MySQLDateTime(fsp=6),
        server_default=text("CURRENT_TIMESTAMP(6)"),
        onupdate=text("CURRENT_TIMESTAMP(6)"),
        nullable=False,
    )
    from_live: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    # Relationships
    station: Mapped["Station"] = relationship(back_populates="items")
    item: Mapped["Item"] = relationship(back_populates="stations")

    __table_args__ = (
        Index("si_itm_dmdpr", "item_id", "demand_price"),
        Index("si_itm_suppr", "item_id", "supply_price"),
        Index("si_fromlive_stn_itm", "from_live", "station_id", "item_id"),
        Index("si_modified", "modified"),
    )


class Ship(Base):
    __tablename__ = "Ship"
    ship_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    cost: Mapped[int | None] = mapped_column(Integer)

    # Relationships
    vendors: Mapped[list["ShipVendor"]] = relationship(back_populates="ship")


class ShipVendor(Base):
    __tablename__ = "ShipVendor"
    ship_id: Mapped[int] = mapped_column(
        ForeignKey("Ship.ship_id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True
    )
    station_id: Mapped[int] = mapped_column(
        ForeignKey("Station.station_id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True
    )
    modified: Mapped[str] = mapped_column(
        MySQLDateTime(fsp=6),
        server_default=text("CURRENT_TIMESTAMP(6)"),
        onupdate=text("CURRENT_TIMESTAMP(6)"),
        nullable=False,
    )

    # Relationships
    ship: Mapped["Ship"] = relationship(back_populates="vendors")
    station: Mapped["Station"] = relationship(back_populates="ship_vendors")

    __table_args__ = (Index("idx_shipvendor_by_station", "station_id"),)


class Upgrade(Base):
    __tablename__ = "Upgrade"
    upgrade_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    class_: Mapped[int] = mapped_column("class", Integer, nullable=False)
    rating: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    ship: Mapped[str | None] = mapped_column(String(40))

    # Relationships
    vendors: Mapped[list["UpgradeVendor"]] = relationship(back_populates="upgrade")


class UpgradeVendor(Base):
    __tablename__ = "UpgradeVendor"
    upgrade_id: Mapped[int] = mapped_column(
        ForeignKey("Upgrade.upgrade_id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True
    )
    station_id: Mapped[int] = mapped_column(
        ForeignKey("Station.station_id", ondelete="CASCADE", onupdate="CASCADE"), primary_key=True
    )
    modified: Mapped[str] = mapped_column(
        MySQLDateTime(fsp=6),
        server_default=text("CURRENT_TIMESTAMP(6)"),
        onupdate=text("CURRENT_TIMESTAMP(6)"),
        nullable=False,
    )

    # Relationships
    upgrade: Mapped["Upgrade"] = relationship(back_populates="vendors")
    station: Mapped["Station"] = relationship(back_populates="upgrade_vendors")

    __table_args__ = (Index("idx_vendor_by_station_id", "station_id"),)


class RareItem(Base):
    __tablename__ = "RareItem"
    rare_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("Station.station_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("Category.category_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    cost: Mapped[int | None] = mapped_column(Integer)
    max_allocation: Mapped[int | None] = mapped_column(Integer)
    illegal: Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))
    suppressed: Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))

    __table_args__ = (UniqueConstraint("name", name="uq_rareitem_name"),)


# ---------- Control & Staging ----------

class ExportControl(Base):
    """
    Singleton control row for hybrid export/watermarking.
    - id: always 1
    - last_full_dump_time: watermark
    - last_reset_key: optional cursor for chunked from_live resets
    """
    __tablename__ = "ExportControl"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, server_default=text("1"))
    last_full_dump_time: Mapped[str] = mapped_column(MySQLDateTime(fsp=6), nullable=False)
    last_reset_key: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class StationItemStaging(Base):
    """
    Staging table for bulk loads (no FKs). Same columns as StationItem.
    """
    __tablename__ = "StationItem_staging"
    station_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    demand_price: Mapped[int] = mapped_column(Integer, nullable=False)
    demand_units: Mapped[int] = mapped_column(Integer, nullable=False)
    demand_level: Mapped[int] = mapped_column(Integer, nullable=False)
    supply_price: Mapped[int] = mapped_column(Integer, nullable=False)
    supply_units: Mapped[int] = mapped_column(Integer, nullable=False)
    supply_level: Mapped[int] = mapped_column(Integer, nullable=False)
    modified: Mapped[str] = mapped_column(
        MySQLDateTime(fsp=6),
        server_default=text("CURRENT_TIMESTAMP(6)"),
        onupdate=text("CURRENT_TIMESTAMP(6)"),
        nullable=False,
    )
    from_live: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    # Optional helper index for merge step; Primary Key already covers this signature.
    __table_args__ = (
        Index("idx_sistaging_stn_itm", "station_id", "item_id"),
    )


__all__ = [
    # Base
    "Base",
    # Core
    "Added",
    "System",
    "Station",
    "Category",
    "Item",
    "StationItem",
    "Ship",
    "ShipVendor",
    "Upgrade",
    "UpgradeVendor",
    "RareItem",
    # Control & staging
    "ExportControl",
    "StationItemStaging",
]
