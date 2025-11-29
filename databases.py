# databases.py
# ---------------------------------------------------------

from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timedelta


# =========================================================
# 1. BASE ITEMS (BUY)
# =========================================================
BaseItemBase = declarative_base()
base_engine = create_engine("sqlite:///base.db", connect_args={"check_same_thread": False})
BaseItemSession = sessionmaker(bind=base_engine)

class BaseItem(BaseItemBase):
    __tablename__ = "base_items"

    id = Column(Integer, primary_key=True)             # Auto-increment ID
    name = Column(String, nullable=False)              # Item name
    vendor = Column(String, default="")                # Supplier/vendor name
    unit_price = Column(Float, default=0.0)            # Purchase cost per unit
    qty_in_stock = Column(Float, default=0.0)          # Available stock quantity

    def __repr__(self):
        return f"<BaseItem id={self.id} name={self.name} vendor={self.vendor} price={self.unit_price} qty={self.qty_in_stock}>"

# Create database
BaseItemBase.metadata.create_all(base_engine)


# =========================================================
# 2. COMPONENTS (MAKE)
# =========================================================
ComponentBase = declarative_base()
component_engine = create_engine("sqlite:///components.db", connect_args={"check_same_thread": False})
ComponentSession = sessionmaker(bind=component_engine)

class Component(ComponentBase):
    __tablename__ = "components"

    id = Column(Integer, primary_key=True)
    sku = Column(String, unique=True, index=True)       # e.g., ITEM-A
    name = Column(String)
    lead_time = Column(Integer, default=0)
    qty_in_stock = Column(Float, default=0.0)          # Available stock quantity

    # Relationship: this component’s BOM lines
    bom_lines = relationship("ComponentBOM", back_populates="parent", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Component sku={self.sku} name={self.name}>"

class ComponentBOM(ComponentBase):
    __tablename__ = "component_boms"

    id = Column(Integer, primary_key=True)
    parent_sku = Column(String, ForeignKey("components.sku"))
    child_sku = Column(String)          # Can reference a base item OR another component
    qty_per = Column(Float)
    source_type = Column(String)        # "base" or "component" — tells recursion where to look

    parent = relationship("Component", back_populates="bom_lines")

    def __repr__(self):
        return f"<BOM {self.parent_sku} ← {self.child_sku} x{self.qty_per} ({self.source_type})>"

# Create database tables
ComponentBase.metadata.create_all(component_engine)

# =========================================================
# 3. PRODUCTION SCHEDULE (TASK LIST)
# =========================================================

ScheduleBase = declarative_base()
schedule_engine = create_engine("sqlite:///schedule.db", connect_args={"check_same_thread": False})
ScheduleSession = sessionmaker(bind=schedule_engine)

class ProductionTask(ScheduleBase):
    __tablename__ = "production_tasks"

    id = Column(Integer, primary_key=True)
    component_sku = Column(String)
    quantity = Column(Integer, default=1)
    status = Column(String, default="pending")
    created_at = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))

    def __repr__(self):
        return f"<Task {self.id} {self.component_sku} x{self.quantity} {self.status}>"

    @property
    def estimated_completion(self):
        """Compute ETA using (lead_time × quantity)."""
        from databases import ComponentSession, Component
        comp_session = ComponentSession()
        comp = comp_session.query(Component).filter_by(sku=self.component_sku).first()
        if not comp:
            return "-"
        try:
            start = datetime.strptime(self.created_at, "%Y-%m-%d %H:%M")
            total_hours = (comp.lead_time or 0) * self.quantity
            eta = start + timedelta(hours=total_hours)
            return eta.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "-"


    def __repr__(self):
        return f"<Task {self.id} {self.component_sku} {self.status}>"

ScheduleBase.metadata.create_all(schedule_engine)