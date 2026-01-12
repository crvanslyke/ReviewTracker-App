import unittest
import sqlite3
import tempfile
import shutil
import csv
from pathlib import Path
from editorial_tracker import init_db, add_item, list_items, update_item, export_csv

class TestEditorialTracker(unittest.TestCase):
    def setUp(self):
        # Use an in-memory database for testing
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        init_db(self.connection)

    def tearDown(self):
        self.connection.close()

    def test_add_and_list_item(self):
        add_item(
            self.connection,
            title="Test Paper",
            reference_id="REF123",
            role="Reviewer",
            venue="Journal A",
            due_date="2024-01-01",
            status="invited",
            decision=None,
            notes="Test notes"
        )
        
        rows = list(list_items(self.connection, status=None))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Test Paper")
        self.assertEqual(rows[0]["reference_id"], "REF123")
        self.assertEqual(rows[0]["venue"], "Journal A")

    def test_list_items_filtering(self):
        add_item(self.connection, title="Paper 1", reference_id=None, role=None, venue=None, due_date=None, status="active", decision=None, notes=None)
        add_item(self.connection, title="Paper 2", reference_id=None, role=None, venue=None, due_date=None, status="completed", decision=None, notes=None)

        active_items = list(list_items(self.connection, status="active"))
        self.assertEqual(len(active_items), 1)
        self.assertEqual(active_items[0]["title"], "Paper 1")

    def test_list_items_sorting(self):
        add_item(self.connection, title="Paper A", reference_id=None, role=None, venue="Venue Z", due_date="2024-03-01", status=None, decision=None, notes=None)
        add_item(self.connection, title="Paper B", reference_id=None, role=None, venue="Venue A", due_date="2024-01-01", status=None, decision=None, notes=None)

        # Default sort (by due date)
        rows_date = list(list_items(self.connection, status=None, sort_by="due-date"))
        self.assertEqual(rows_date[0]["title"], "Paper B") # Earlier date first
        self.assertEqual(rows_date[1]["title"], "Paper A")

        # Sort by venue
        rows_venue = list(list_items(self.connection, status=None, sort_by="venue"))
        self.assertEqual(rows_venue[0]["title"], "Paper B") # Venue A
        self.assertEqual(rows_venue[1]["title"], "Paper A") # Venue Z

    def test_update_item(self):
        add_item(self.connection, title="Original Title", reference_id=None, role=None, venue=None, due_date=None, status="invited", decision=None, notes=None)
        rows = list(list_items(self.connection, status=None))
        item_id = rows[0]["id"]

        update_item(self.connection, item_id, title="Updated Title", status="in_progress")
        
        updated_rows = list(list_items(self.connection, status=None))
        self.assertEqual(updated_rows[0]["title"], "Updated Title")
        self.assertEqual(updated_rows[0]["status"], "in_progress")

    def test_export_csv(self):
        add_item(self.connection, title="CSV Paper", reference_id="CSV1", role=None, venue=None, due_date=None, status=None, decision=None, notes=None)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_export.csv"
            export_csv(self.connection, output_path)
            
            self.assertTrue(output_path.exists())
            with open(output_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["title"], "CSV Paper")

if __name__ == "__main__":
    unittest.main()
