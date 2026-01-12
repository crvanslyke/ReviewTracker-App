from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select
from typing import Optional, List
from datetime import datetime
import os

# --------------------------------------------------------------------------------
# DATA MODELS
# --------------------------------------------------------------------------------

class WorkItem(SQLModel, table=True):
    __tablename__ = "work_items"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    reference_id: Optional[str] = Field(default=None, index=True)
    venue: Optional[str] = Field(default=None, index=True)
    due_date: Optional[str] = Field(default=None, index=True) # ISO Date String YYYY-MM-DD
    role: Optional[str] = Field(default=None) # Reviewer, AE, Chair, etc.
    status: str = Field(default="invited", index=True) # invited, active, submitted, etc.
    decision: Optional[str] = Field(default=None) # accept, reject, revision
    notes: Optional[str] = Field(default=None)
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

# API Request Models
class ItemCreate(BaseModel):
    title: str
    venue: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = "invited"
    role: Optional[str] = None
    reference_id: Optional[str] = None
    decision: Optional[str] = None
    notes: Optional[str] = None

class ItemUpdate(BaseModel):
    title: Optional[str] = None
    venue: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = None
    role: Optional[str] = None
    reference_id: Optional[str] = None
    decision: Optional[str] = None
    notes: Optional[str] = None

# --------------------------------------------------------------------------------
# DATABASE
# --------------------------------------------------------------------------------

# Handle Vercel's 'postgres://' quirk for SQLAlchemy
db_url = os.environ.get("DATABASE_URL", "sqlite:///editorial_tracker.db")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

# --------------------------------------------------------------------------------
# APP & ROUTES
# --------------------------------------------------------------------------------

app = FastAPI()

# Vercel Serverless Optimization: Init DB on app startup
@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/api/items", response_model=List[WorkItem])
def read_items(session: Session = Depends(get_session)):
    items = session.exec(select(WorkItem).order_by(WorkItem.due_date)).all()
    return items

@app.get("/api/venues")
def read_venues(session: Session = Depends(get_session)):
    # Distinct venues via Python (simpler for SQLite/PG compatibility without complex queries)
    items = session.exec(select(WorkItem)).all()
    venues = sorted(list(set(i.venue for i in items if i.venue)))
    return venues

@app.post("/api/items")
def create_item(item: ItemCreate, session: Session = Depends(get_session)):
    db_item = WorkItem.model_validate(item)
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item

@app.patch("/api/items/{item_id}")
def update_item_endpoint(item_id: int, item: ItemUpdate, session: Session = Depends(get_session)):
    db_item = session.get(WorkItem, item_id)
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    item_data = item.model_dump(exclude_unset=True)
    for key, value in item_data.items():
        setattr(db_item, key, value)
    
    db_item.updated_at = datetime.now()
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item

@app.delete("/api/items/{item_id}")
def delete_item(item_id: int, session: Session = Depends(get_session)):
    db_item = session.get(WorkItem, item_id)
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    session.delete(db_item)
    session.commit()
    return {"ok": True}
