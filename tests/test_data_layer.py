"""
Unit tests for DataLayer (DuckDB)
"""
import pytest
import sys
from pathlib import Path
import tempfile
import os

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data_layer import DataLayer


class TestDataLayer:
    """Test DuckDB data layer"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            layer = DataLayer(db_path=db_path)
            yield layer
            layer.close()
    
    def test_init_schema(self, temp_db):
        """Test schema initialization"""
        temp_db.init_schema()
        
        # Check that tables exist
        tables = temp_db.query(
            "SELECT name FROM duckdb_tables() WHERE type = 'table'"
        )
        table_names = [row[0] if isinstance(row, tuple) else row for row in tables]
        
        # Should have at least core tables
        assert len(table_names) > 0
    
    def test_insert_student(self, temp_db):
        """Test inserting a student"""
        temp_db.init_schema()
        
        student_data = {
            "student_id": "S001",
            "archive_json": {"name": "张三", "grade": 8},
            "simulation_vector": {"p_know": 0.5, "p_learn": 0.25},
            "sensitive_json": {"health": "normal"},
            "identity_fingerprint": "fp123",
            "llm_generated_fields": {"name": True},
            "class_id": "C001",
            "assigned_teacher_id": "T001",
            "primary_parent_id": "P001",
            "seed": 42,
            "created_at": 1234567890
        }
        
        temp_db.insert_student(student_data)
        temp_db.commit()
        
        # Verify insert
        result = temp_db.query("SELECT COUNT(*) FROM students")
        assert result[0][0] == 1
    
    def test_insert_real_log(self, temp_db):
        """Test inserting real learning log"""
        temp_db.init_schema()
        
        log_data = {
            "log_id": "L001",
            "learner_id": "real_001",
            "kc_id": "K001",
            "item_id": "I001",
            "is_correct": True,
            "response_time_sec": 5.2,
            "timestamp_ms": 1234567890000,
            "session_id": "S123"
        }
        
        temp_db.insert_real_log(log_data)
        temp_db.commit()
        
        # Verify insert
        result = temp_db.query("SELECT COUNT(*) FROM real_logs")
        assert result[0][0] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
