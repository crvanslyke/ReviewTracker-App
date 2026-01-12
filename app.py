import streamlit as st
import pandas as pd
from sqlmodel import Session, select
from datetime import datetime

# Import backend logic
from editorial_tracker import get_engine, WorkItem, add_item, update_item, get_venues

# Page Config
st.set_page_config(
    page_title="ReviewTracker",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize DB connection
engine = get_engine()

# --- Helper Functions ---
def get_data():
    with Session(engine) as session:
        statement = select(WorkItem)
        items = session.exec(statement).all()
        # Convert to list of dicts for DataFrame
        data = [item.model_dump() for item in items]
    return data

def save_changes(edited_rows, original_data):
    """
    Handle changes from st.data_editor.
    edited_rows: dict of {index: {col: new_value}}
    original_data: DataFrame containing the data being edited
    """
    with Session(engine) as session:
        for idx, changes in edited_rows.items():
            # Get the actual ID from the dataframe
            # Note: idx is the row index in the current view/dataframe, not necessarily the DB ID
            # We must map it back to the 'id' column of the dataframe
            item_id = original_data.iloc[idx]['id']
            # Only send valid fields to update_item
            update_item(session, int(item_id), **changes)

# --- Sidebar: Add New Item ---
with st.sidebar:
    st.header("New Entry")
    with st.form("add_item_form", clear_on_submit=True):
        title = st.text_input("Title")
        ref_id = st.text_input("Manuscript ID")
        venue = st.text_input("Venue (Journal/Conf)")
        role = st.selectbox("Role", ["Reviewer", "Associate Editor", "Chair", "Author"])
        status = st.selectbox("Status", ["invited", "active", "in_review", "pending", "completed", "accepted", "rejected"])
        due_date = st.date_input("Due Date")
        
        submitted = st.form_submit_button("Add Item")
        if submitted and title:
            with Session(engine) as session:
                add_item(
                    session, 
                    title=title, 
                    reference_id=ref_id,
                    role=role,
                    venue=venue,
                    status=status,
                    due_date=str(due_date)
                )
            st.success("Added!")
            st.rerun()

# --- Main Dashboard ---
st.title("📝 Editorial & Review Tracker")

# load data
raw_data = get_data()
if not raw_data:
    df = pd.DataFrame(columns=["id", "title", "reference_id", "venue", "role", "status", "due_date", "decision", "notes"])
else:
    df = pd.DataFrame(raw_data)
    # Convert due_date to datetime objects for the DateColumn editor
    if "due_date" in df.columns:
        df["due_date"] = pd.to_datetime(df["due_date"], errors='coerce')

# --- Metric Row ---
col1, col2, col3, col4 = st.columns(4)
active_count = len(df[df['status'].isin(['active', 'invited', 'in_review'])])
pending_count = len(df[df['status'] == 'pending'])
completed_count = len(df[df['status'].isin(['completed', 'accepted', 'rejected'])])
upcoming_deadlines = len(df) # Placeholder logic, refine if needed

col1.metric("Active Reviews", active_count)
col2.metric("Pending Decisions", pending_count)
col3.metric("Completed", completed_count)
# col4.metric("Upcoming", upcoming_deadlines) # You could calculate this based on dates

st.divider()

# --- Interactive Table ---
st.subheader("Work Items")

# Configure Columns for Editor
column_config = {
    "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
    "title": st.column_config.TextColumn("Title", width="large"),
    "status": st.column_config.SelectboxColumn(
        "Status",
        options=["invited", "active", "in_review", "pending", "completed", "accepted", "rejected"],
        width="medium",
        required=True
    ),
    "venue": st.column_config.TextColumn("Venue"),
    "due_date": st.column_config.DateColumn("Due Date", format="YYYY-MM-DD"),
    "role": st.column_config.SelectboxColumn("Role", options=["Reviewer", "AE", "Chair", "Author"]),
    "notes": st.column_config.TextColumn("Notes"),
}

# Display Editor
edited_df = st.data_editor(
    df,
    column_config=column_config,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed", # Prevent adding rows here (use sidebar) to avoid ID complexities
    key="editor"
)

# Detect changes manually? 
# actually st.data_editor in current version doesn't auto-callback well without session state hacks
# OR, simpler: We can just diff the dataframes?
# But st.data_editor returns the *edited* dataframe.
# We can iterate and update. BUT it's heavy to diff every run.
# A better pattern for small apps:
# Use on_change callback? No, data_editor doesn't support generic on_change for cell edits easily.
# Let's simple check if `edited_df` differs from `df`?
# NO, wait. `st.data_editor` has an `on_change` in newer versions?
# Actually, let's keep it simple. The edits in the UI persist in the UI state.
# But we need to save to DB.
# The `st.data_editor` returns the modified frame.
# We should compare it to DB? Or provided a "Save Changes" button?
# "Auto-save" is tricky with SQL interactions on every keystroke.
# Let's add a "Save Changes" button if we detect changes, OR just blindly update changed rows if possible.
# Actually, the best way for Streamlit < 1.30 was session state.
# But let's assume standard usage:
# The user edits -> hits enter -> script reruns -> `edited_df` has new values.
# We need to know *what* changed to update the DB efficiently, OR we just iterate and update all.
# Since the dataset is small (<1000 items likely), iterating and updating modified IDs is fine.

# Let's perform a smart update:
# Iterate through edited_df, find corresponding row in DB, if different, update.
# This happens on every interaction, so it might be "chatty" with the DB but gives the "Instant Update" feel.

if not df.equals(edited_df):
    # Find changed rows
    # This comparison requires implementation.
    # Simpler approach: Just update *everything*? No.
    # Let's utilize the fact that `st.data_editor` state is preserved.
    # Actually, let's rely on a "Save Changes" button for stability, OR auto-save.
    # Let's try auto-save by iterating.
    
    with Session(engine) as session:
        for index, row in edited_df.iterrows():
            # Check against original df to see if this row changed?
            # Or just blindly update. SQLModel update is cheap if fields match.
            # But we need to handle type conversions.
            
            # Simple check:
            original_row = df[df['id'] == row['id']].iloc[0] if not df.empty else None
            if original_row is not None and not row.equals(original_row):
               # This row changed
               update_item(
                   session, 
                   int(row['id']), 
                   title=row['title'],
                   status=row['status'],
                   venue=row['venue'],
                   role=row['role'],
                   notes=row['notes'],
                   # Date needs care, might be date object or string
                   due_date=str(row['due_date']) if row['due_date'] else None
               )
    
    # st.toast("Changes saved!") # Nice feedback
    # We might need to reload `df` to sync state? 
    # If we `st.rerun()`, it might loop if we aren't careful.
    # But since we updated DB, `get_data()` will return new data next time.
    # So `df` becomes `edited_df`. Stability reached.
    pass

