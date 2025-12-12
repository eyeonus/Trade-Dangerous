# tradedangerous/db/orm_models.py
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import (
    MetaData,
    ForeignKey,
    Integer,
    BigInteger,
    String,
    CHAR,
    Enum,
    Index,
    UniqueConstraint,
    CheckConstraint,
    text,
    Column,
    DateTime,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, object_session
from sqlalchemy.sql import expression
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import TypeDecorator


# ---- Dialect-aware time utilities (moved before model usage) ----
class now6(expression.FunctionElement):
    """CURRENT_TIMESTAMP with microseconds on MySQL/MariaDB; plain CURRENT_TIMESTAMP elsewhere."""
    type = DateTime()
    inherit_cache = True


@compiles(now6, "mysql")
@compiles(now6, "mariadb")
def _mysql_now6(element, compiler, **kw):
    return "CURRENT_TIMESTAMP(6)"


@compiles(now6)
def _default_now(element, compiler, **kw):
    return "CURRENT_TIMESTAMP"


class DateTime6(TypeDecorator):
    """DATETIME that is DATETIME(6) on MySQL/MariaDB, generic DateTime elsewhere. Always UTC."""
    impl = DateTime
    cache_ok = True
    
    def load_dialect_impl(self, dialect):
        if dialect.name in ("mysql", "mariadb"):
            from sqlalchemy.dialects.mysql import DATETIME as _MYSQL_DATETIME
            return dialect.type_descriptor(_MYSQL_DATETIME(fsp=6))
        return dialect.type_descriptor(DateTime(timezone=True))
    
    def process_result_value(self, value, dialect):
        """Ensure all datetimes loaded from DB are UTC-aware."""
        if value is not None and value.tzinfo is None:
            # Database stored naive datetime; treat it as UTC
            return value.replace(tzinfo=datetime.timezone.utc)
        return value


# ---------- Dialect Helpers --------
class CIString(TypeDecorator):
    """
    Case-insensitive string type.
    - SQLite → uses NOCASE collation
    - MySQL/MariaDB → uses utf8mb4_unicode_ci
    - Others → plain String
    """
    impl = String
    cache_ok = True
    
    def __init__(self, length, **kwargs):
        super().__init__(length=length, **kwargs)
    
    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            return dialect.type_descriptor(String(self.impl.length, collation="NOCASE"))
        elif dialect.name in ("mysql", "mariadb"):
            return dialect.type_descriptor(String(self.impl.length, collation="utf8mb4_unicode_ci"))
        else:
            return dialect.type_descriptor(String(self.impl.length))


# ---------- Naming & Base ----------
naming_convention = {
    "ix": "ix_%(table_name)s__%(column_0_N_name)s",
    "uq": "uq_%(table_name)s__%(column_0_N_name)s",
    "ck": "ck_%(table_name)s__%(column_0_name)s",   # use column name, not constraint_name
    "fk": "fk_%(table_name)s__%(column_0_N_name)s__%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=naming_convention)


class Base(DeclarativeBase):
    metadata = metadata

# ---------- Enums ----------
TriState = Enum(
    "Y",
    "N",
    "?",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)

PadSize = Enum(
    "S",
    "M",
    "L",
    "?",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)


# ---------- Core Domain ----------
class Added(Base):
    __tablename__ = "Added"
    
    added_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(CIString(128), nullable=False, unique=True)
    
    # Relationships
    systems: Mapped[list["System"]] = relationship(back_populates="added")


class System(Base):
    __tablename__ = "System"
    
    system_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(CIString(128), nullable=False)
    pos_x: Mapped[float] = mapped_column(nullable=False)
    pos_y: Mapped[float] = mapped_column(nullable=False)
    pos_z: Mapped[float] = mapped_column(nullable=False)
    added_id: Mapped[int | None] = mapped_column(
        ForeignKey("Added.added_id", onupdate="CASCADE", ondelete="CASCADE")
    )
    modified: Mapped[str] = mapped_column(
        DateTime6(),
        server_default=now6(),
        onupdate=now6(),
        nullable=False,
    )
    
    def dbname(self) -> str:
        return f"{self.name.upper()}/"
    
    # Relationships
    added: Mapped[Optional["Added"]] = relationship(back_populates="systems")
    stations: Mapped[list["Station"]] = relationship(back_populates="system", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_system_by_pos", "pos_x", "pos_y", "pos_z", "system_id"),
        Index("idx_system_by_name", "name"),
    )




class Station(Base):
    __tablename__ = "Station"
    
    station_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(CIString(128), nullable=False)
    
    def dbname(self) -> str:
        return f"{self.system.name}/{self.name}"
    
    # type widened; cascade semantics unchanged (DELETE only)
    system_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("System.system_id", ondelete="CASCADE"),
        nullable=False,
    )
    
    ls_from_star: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    
    blackmarket: Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))
    max_pad_size: Mapped[str] = mapped_column(PadSize, nullable=False, server_default=text("'?'"))
    market: Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))
    shipyard: Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))
    outfitting: Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))
    rearm: Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))
    refuel: Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))
    repair: Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))
    planetary: Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))
    
    type_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    modified: Mapped[str] = mapped_column(DateTime6(), server_default=now6(), onupdate=now6(), nullable=False)
    
    # Relationships
    system: Mapped["System"] = relationship(back_populates="stations")
    items: Mapped[list["StationItem"]] = relationship(back_populates="station", cascade="all, delete-orphan")
    ship_vendors: Mapped[list["ShipVendor"]] = relationship(back_populates="station", cascade="all, delete-orphan")
    upgrade_vendors: Mapped[list["UpgradeVendor"]] = relationship(back_populates="station", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_station_by_system", "system_id"),
        Index("idx_station_by_name", "name"),
    )




class Category(Base):
    __tablename__ = "Category"
    
    category_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(CIString(128), nullable=False)
    
    # Relationships
    items: Mapped[list["Item"]] = relationship(back_populates="category")
    
    __table_args__ = (Index("idx_category_by_name", "name"),)


class Item(Base):
    __tablename__ = "Item"
    
    item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(CIString(128), nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("Category.category_id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    def dbname(self, detail: int | bool = 0) -> str:
        if detail:
            return f"{self.category.name}/{self.name}"
        return self.name
    ui_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    avg_price: Mapped[int | None] = mapped_column(Integer)
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
        BigInteger,
        ForeignKey("Station.station_id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("Item.item_id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    demand_price: Mapped[int] = mapped_column(Integer, nullable=False)
    demand_units: Mapped[int] = mapped_column(Integer, nullable=False)
    demand_level: Mapped[int] = mapped_column(Integer, nullable=False)
    supply_price: Mapped[int] = mapped_column(Integer, nullable=False)
    supply_units: Mapped[int] = mapped_column(Integer, nullable=False)
    supply_level: Mapped[int] = mapped_column(Integer, nullable=False)
    modified: Mapped[str] = mapped_column(DateTime6(), server_default=now6(), onupdate=now6(), nullable=False)
    from_live: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    
    # Relationships
    station: Mapped["Station"] = relationship(back_populates="items")
    item: Mapped["Item"] = relationship(back_populates="stations")
    
    __table_args__ = (
        Index("si_mod_stn_itm", "modified", "station_id", "item_id"),
        Index("si_itm_dmdpr", "item_id", "demand_price", sqlite_where=text("demand_price > 0")),
        Index("si_itm_suppr", "item_id", "supply_price", sqlite_where=text("supply_price > 0")),
        {"sqlite_with_rowid": False},
    )




class Ship(Base):
    __tablename__ = "Ship"
    
    ship_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(CIString(128), nullable=False)
    cost: Mapped[int | None] = mapped_column(Integer)
    
    # Relationships
    vendors: Mapped[list["ShipVendor"]] = relationship(back_populates="ship")


class ShipVendor(Base):
    __tablename__ = "ShipVendor"
    
    ship_id: Mapped[int] = mapped_column(
        ForeignKey("Ship.ship_id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    station_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("Station.station_id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    modified: Mapped[str] = mapped_column(DateTime6(), server_default=now6(), onupdate=now6(), nullable=False)
    
    # Relationships
    ship: Mapped["Ship"] = relationship(back_populates="vendors")
    station: Mapped["Station"] = relationship(back_populates="ship_vendors")
    
    __table_args__ = (Index("idx_shipvendor_by_station", "station_id"),)


class Upgrade(Base):
    __tablename__ = "Upgrade"
    
    upgrade_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(CIString(128), nullable=False)
    class_: Mapped[int] = mapped_column("class", Integer, nullable=False)
    rating: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    ship: Mapped[str | None] = mapped_column(CIString(128))
    
    # Relationships
    vendors: Mapped[list["UpgradeVendor"]] = relationship(back_populates="upgrade")


class UpgradeVendor(Base):
    __tablename__ = "UpgradeVendor"
    
    upgrade_id: Mapped[int] = mapped_column(
        ForeignKey("Upgrade.upgrade_id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    station_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("Station.station_id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    modified: Mapped[str] = mapped_column(DateTime6(), nullable=False, server_default=now6(), onupdate=now6())
    
    # Relationships
    upgrade: Mapped["Upgrade"] = relationship(back_populates="vendors")
    station: Mapped["Station"] = relationship(back_populates="upgrade_vendors")
    
    __table_args__ = (Index("idx_vendor_by_station_id", "station_id"),)


class RareItem(Base):
    __tablename__ = "RareItem"
    
    rare_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("Station.station_id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("Category.category_id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(CIString(128), nullable=False)
    cost: Mapped[int | None] = mapped_column(Integer)
    max_allocation: Mapped[int | None] = mapped_column(Integer)
    illegal: Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))
    suppressed: Mapped[str] = mapped_column(TriState, nullable=False, server_default=text("'?'"))
    
    __table_args__ = (UniqueConstraint("name", name="uq_rareitem_name"),)




class FDevShipyard(Base):
    __tablename__ = "FDevShipyard"
    
    id = Column(Integer, primary_key=True, unique=True, nullable=False)
    symbol = Column(CIString(128))
    name = Column(CIString(128))
    entitlement = Column(String(50))


class FDevOutfitting(Base):
    __tablename__ = "FDevOutfitting"
    
    id = Column(Integer, primary_key=True, unique=True, nullable=False)
    symbol = Column(CIString(128))
    category = Column(String(10))
    name = Column(CIString(128))
    mount = Column(String(20))
    guidance = Column(String(20))
    ship = Column(CIString(128))
    class_ = Column("class", String(1), nullable=False)
    rating = Column(String(1), nullable=False)
    entitlement = Column(String(50))
    
    __table_args__ = (
        CheckConstraint(
            "category IN ('hardpoint','internal','standard','utility')",
            name="ck_fdo_category",
        ),
        CheckConstraint(
            "(mount IN ('Fixed','Gimballed','Turreted')) OR (mount IS NULL)",
            name="ck_fdo_mount",
        ),
        CheckConstraint(
            "(guidance IN ('Dumbfire','Seeker','Swarm')) OR (guidance IS NULL)",
            name="ck_fdo_guidance",
        ),
    )


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
    last_full_dump_time: Mapped[str] = mapped_column(DateTime6(), nullable=False)
    last_reset_key: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class StationItemStaging(Base):
    """
    Staging table for bulk loads (no FKs). Same columns as StationItem.
    """
    __tablename__ = "StationItem_staging"
    
    station_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    demand_price: Mapped[int] = mapped_column(Integer, nullable=False)
    demand_units: Mapped[int] = mapped_column(Integer, nullable=False)
    demand_level: Mapped[int] = mapped_column(Integer, nullable=False)
    supply_price: Mapped[int] = mapped_column(Integer, nullable=False)
    supply_units: Mapped[int] = mapped_column(Integer, nullable=False)
    supply_level: Mapped[int] = mapped_column(Integer, nullable=False)
    modified: Mapped[str] = mapped_column(DateTime6(), server_default=now6(), onupdate=now6(), nullable=False)
    from_live: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    
    __table_args__ = (Index("idx_sistaging_stn_itm", "station_id", "item_id"),)




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
    "FDevShipyard",
    "FDevOutfitting",
    # Control & staging
    "ExportControl",
    "StationItemStaging",
]
