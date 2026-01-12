import sys
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

# Add the parent directory to sys.path to import editorial_tracker
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from editorial_tracker import init_db, add_item, list_items, update_item, connect, get_venues

app = FastAPI()

# On Vercel, only /tmp is writable.
# We will use a temporary database file.
# NOTE: Data will persist only as long as the container is hot.
DB_PATH = Path("/tmp/editorial_tracker.db")

def get_connection():
    ensure_db_init()
    return connect(DB_PATH)

def ensure_db_init():
    if not DB_PATH.exists():
        conn = connect(DB_PATH)
        init_db(conn)
        conn.close()

# Models
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

@app.get("/api/items")
def read_items(sort: str = "due-date", order: str = "ASC"):
    conn = get_connection()
    try:
        rows = list_items(conn, status=None, sort_by=sort, sort_order=order)
        return [dict(row) for row in rows]
    finally:
        conn.close()

@app.get("/api/venues")
def read_venues():
    conn = get_connection()
    try:
        return get_venues(conn)
    finally:
        conn.close()

@app.post("/api/items")
def create_item(item: ItemCreate):
    conn = get_connection()
    try:
        add_item(
            conn,
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
    finally:
        conn.close()

@app.patch("/api/items/{item_id}")
def update_item_endpoint(item_id: int, item: ItemUpdate):
    conn = get_connection()
    try:
        update_data = item.dict(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_item(conn, item_id, **update_data)
        return {"message": "Item updated"}
    finally:
        conn.close()

# Serve static files (HTML frontend)
# Note: In a real Vercel + FastAPI setup, often static files are served by Vercel directly, 
# but this allows local testing and simple serving.
app.mount("/", StaticFiles(directory="public", html=True), name="public")
