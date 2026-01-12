import unittest
import shutil
import csv
from pathlib import Path
from sqlmodel import Session, create_engine, SQLModel, select
from api.editorial_tracker import init_db, add_item, list_items, update_item, export_csv, WorkItem, get_engine

class TestEditorialTracker(unittest.TestCase):
    def setUp(self):
        # Use an in-memory database for testing
        self.engine = create_engine("sqlite:///:memory:")
        init_db(self.engine)
        self.session = Session(self.engine)

    def tearDown(self):
        self.session.close()

    def test_add_and_list_item(self):
        add_item(
            self.session,
            title="Test Paper",
            reference_id="REF123",
            role="Reviewer",
            venue="Journal A",
            due_date="2024-01-01",
            status="invited",
            decision=None,
            notes="Test notes"
        )
        
        # SQLModel returns model instances
        rows = list_items(self.session, status=None)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].title, "Test Paper")
        self.assertEqual(rows[0].reference_id, "REF123")
        self.assertEqual(rows[0].venue, "Journal A")

    def test_list_items_filtering(self):
        # Helper to add simple items
        add_item(self.session, title="Paper 1", reference_id=None, role=None, venue=None, due_date=None, status="active", decision=None, notes=None)
        add_item(self.session, title="Paper 2", reference_id=None, role=None, venue=None, due_date=None, status="completed", decision=None, notes=None)

        active_items = list_items(self.session, status="active")
        self.assertEqual(len(active_items), 1)
        self.assertEqual(active_items[0].title, "Paper 1")

    def test_list_items_sorting(self):
        add_item(self.session, title="Paper A", reference_id=None, role=None, venue="Venue Z", due_date="2024-03-01", status=None, decision=None, notes=None)
        add_item(self.session, title="Paper B", reference_id=None, role=None, venue="Venue A", due_date="2024-01-01", status=None, decision=None, notes=None)

        # Default sort (by due date)
        rows_date = list_items(self.session, status=None, sort_by="due_date")
        self.assertEqual(rows_date[0].title, "Paper B") # Earlier date first
        self.assertEqual(rows_date[1].title, "Paper A")

        # Sort by venue
        rows_venue = list_items(self.session, status=None, sort_by="venue")
        self.assertEqual(rows_venue[0].title, "Paper B") # Venue A
        self.assertEqual(rows_venue[1].title, "Paper A") # Venue Z

    def test_update_item(self):
        add_item(self.session, title="Original Title", reference_id=None, role=None, venue=None, due_date=None, status="invited", decision=None, notes=None)
        rows = list_items(self.session, status=None)
        item_id = rows[0].id

        update_item(self.session, item_id, title="Updated Title", status="in_progress")
        
        updated_item = self.session.get(WorkItem, item_id)
        self.assertEqual(updated_item.title, "Updated Title")
        self.assertEqual(updated_item.status, "in_progress")

    def test_export_csv(self):
        add_item(self.session, title="CSV Paper", reference_id="CSV1", role=None, venue=None, due_date=None, status=None, decision=None, notes=None)
        
        output_path = Path("test_export.csv")
        try:
            export_csv(self.session, output_path)
            
            self.assertTrue(output_path.exists())
            with open(output_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["title"], "CSV Paper")
        finally:
            if output_path.exists():
                output_path.unlink()

if __name__ == "__main__":
    unittest.main()
