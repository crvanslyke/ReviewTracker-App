import sys
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
from sqlmodel import Session, select

# Add the parent directory to sys.path to import editorial_tracker
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from editorial_tracker import init_db, add_item, list_items, update_item, get_venues, get_engine, WorkItem

app = FastAPI()

# Database Setup
engine = get_engine()

# On Vercel startup (or local), ensure DB tables exist
@app.on_event("startup")
def on_startup():
    init_db(engine)

def get_session():
    with Session(engine) as session:
        yield session

# Models (Pydantic models for API request bodies)
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

@app.get("/api/items", response_model=List[WorkItem])
def read_items(
    sort: str = "due_date", 
    order: str = "ASC", 
    session: Session = Depends(get_session)
):
    # Normalize sort field from frontend (e.g. "due-date" -> "due_date")
    sort_field = sort.replace("-", "_")
    return list_items(session, status=None, sort_by=sort_field, sort_order=order)

@app.get("/api/venues")
def read_venues(session: Session = Depends(get_session)):
    return get_venues(session)

@app.post("/api/items")
def create_item(item: ItemCreate, session: Session = Depends(get_session)):
    add_item(
        session,
        title=item.title,
        reference_id=item.reference_id,
        role=item.role,
        venue=item.venue,
        due_date=item.due_date,
        status=item.status,
        decision=item.decision,
        notes=item.notes
    )
    return {"message": "Item created"}

@app.patch("/api/items/{item_id}")
def update_item_endpoint(
    item_id: int, 
    item: ItemUpdate, 
    session: Session = Depends(get_session)
):
    try:
        update_data = item.dict(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Convert keys if needed (e.g. if frontend sends differently), but here they match
        update_item(session, item_id, **update_data)
        return {"message": "Item updated"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Serve static files (HTML frontend)
app.mount("/", StaticFiles(directory="public", html=True), name="public")
