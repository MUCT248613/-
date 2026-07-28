"""
DuckDB Data Layer - Database schema and initialization
"""
import duckdb
import json
from pathlib import Path
from typing import Dict, List, Optional


class DataLayer:
    """
    DuckDB-based persistent data store
    """
    
    def __init__(self, db_path: str = "data/virtual_student.db"):
        self.db_path = db_path
        self.conn = None
        self._init_connection()
    
    def _init_connection(self):
        """Initialize DuckDB connection"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(self.db_path)
    
    def init_schema(self):
        """Initialize all tables"""
        self._create_real_data_tables()
        self._create_persona_tables()
        self._create_simulation_tables()
        self._create_result_tables()
    
    def _create_real_data_tables(self):
        """Real data from ASSISTments/EdNet"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS real_logs (
                log_id VARCHAR PRIMARY KEY,
                learner_id VARCHAR,
                kc_id VARCHAR,
                item_id VARCHAR,
                is_correct BOOLEAN,
                response_time_sec FLOAT,
                timestamp_ms BIGINT,
                session_id VARCHAR
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS kc_params (
                kc_id VARCHAR PRIMARY KEY,
                p_know_posterior FLOAT,
                p_learn FLOAT,
                p_slip FLOAT,
                p_guess FLOAT,
                data_count INTEGER,
                fit_timestamp BIGINT
            )
        """)
    
    def _create_persona_tables(self):
        """Virtual persona storage (v5.0: LLM-deep-participatory)"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id VARCHAR PRIMARY KEY,
                archive_json JSON,                  -- Full 23-domain narrative archive
                simulation_vector JSON,             -- P/R-level params for cognitive engine
                sensitive_json JSON,                -- S-level fields (health/family/parenting)
                identity_fingerprint VARCHAR,       -- Uniqueness guarantee
                llm_generated_fields JSON,          -- Traceability of LLM participation
                class_id VARCHAR,
                assigned_teacher_id VARCHAR,
                primary_parent_id VARCHAR,
                seed INTEGER,
                created_at BIGINT
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                teacher_id VARCHAR PRIMARY KEY,
                archive_json JSON,                  -- T1-T8 domains
                simulation_vector JSON,             -- T-Model params (fidelity, style_match)
                sensitive_json JSON,
                identity_fingerprint VARCHAR,
                llm_generated_fields JSON,
                seed INTEGER,
                created_at BIGINT
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS parents (
                parent_id VARCHAR PRIMARY KEY,
                archive_json JSON,                  -- P1-P6 domains
                simulation_vector JSON,             -- P-Model params (style_multiplier)
                sensitive_json JSON,
                identity_fingerprint VARCHAR,
                llm_generated_fields JSON,
                student_id VARCHAR,                 -- Associated student
                relation_to_student VARCHAR,
                seed INTEGER,
                created_at BIGINT
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS institutions (
                institution_id VARCHAR PRIMARY KEY,
                type VARCHAR,                       -- school/class/shadow_edu_provider
                archive_json JSON,                  -- I1-I2 domains
                identity_fingerprint VARCHAR,
                llm_generated_fields JSON,
                seed INTEGER,
                created_at BIGINT
            )
        """)
    
    def _create_simulation_tables(self):
        """L-Model and multi-agent simulation state"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_timelines (
                timeline_id VARCHAR PRIMARY KEY,
                student_id VARCHAR,
                sim_date DATE,
                scene_events_json JSON,             -- Five-scene event stream
                total_learning_gain FLOAT,
                fatigue_end FLOAT,
                created_at BIGINT
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS social_networks (
                network_id VARCHAR PRIMARY KEY,
                sim_date DATE,
                edges_json JSON,                    -- Graph edges with types/weights
                metrics_json JSON,
                created_at BIGINT
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                rel_id VARCHAR PRIMARY KEY,
                type VARCHAR,                       -- friendship/romantic/conflict/teacher_student/parent_child
                party_a VARCHAR,
                party_b VARCHAR,
                state VARCHAR,                      -- Current relationship state
                formed_date DATE,
                ended_date DATE,
                quality FLOAT,
                history_json JSON,
                created_at BIGINT
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS life_events (
                event_id VARCHAR PRIMARY KEY,
                student_id VARCHAR,
                event_type VARCHAR,                 -- 30+ event types
                domain VARCHAR,                     -- academic/family/health/social/emotional
                severity INTEGER,
                occurred_date DATE,
                impact_json JSON,
                half_life_weeks FLOAT,
                created_at BIGINT
            )
        """)
    
    def _create_result_tables(self):
        """Simulation results and analysis"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sim_interactions (
                interaction_id VARCHAR PRIMARY KEY,
                run_id VARCHAR,
                student_id VARCHAR,
                intervention_id VARCHAR,
                item_id VARCHAR,
                scene VARCHAR,
                is_correct BOOLEAN,
                p_correct FLOAT,
                learning_gain FLOAT,
                timestamp_min FLOAT,
                delivery_mode VARCHAR
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS virtual_effect_sizes (
                es_id VARCHAR PRIMARY KEY,
                run_id VARCHAR,
                intervention_id VARCHAR,
                hedges_g FLOAT,
                ci_lower FLOAT,
                ci_upper FLOAT,
                scene VARCHAR,
                subgroup_filter JSON,
                sample_size INTEGER
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS gap_records (
                gap_id VARCHAR PRIMARY KEY,
                run_id VARCHAR,
                metric VARCHAR,                     -- Learning curve / error dist / first correct / variance ratio
                real_value FLOAT,
                virtual_value FLOAT,
                gap_magnitude FLOAT,
                distortion_category VARCHAR,        -- Direction of bias
                subgroup_filter JSON
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS run_states (
                run_id VARCHAR PRIMARY KEY,
                status VARCHAR,                     -- initialized → data_loaded → ... → reported
                created_at BIGINT,
                updated_at BIGINT,
                config_json JSON,
                metadata_json JSON
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_calls (
                call_id VARCHAR PRIMARY KEY,
                run_id VARCHAR,
                module VARCHAR,                     -- persona_service / l_model / language_agent / etc
                model VARCHAR,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                cost_yuan FLOAT,
                timestamp_ms BIGINT
            )
        """)
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def insert_real_log(self, log_data: Dict):
        """Insert real learning log"""
        self.conn.execute("""
            INSERT INTO real_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            log_data.get("log_id"),
            log_data.get("learner_id"),
            log_data.get("kc_id"),
            log_data.get("item_id"),
            log_data.get("is_correct"),
            log_data.get("response_time_sec"),
            log_data.get("timestamp_ms"),
            log_data.get("session_id")
        ])
    
    def insert_student(self, student_data: Dict):
        """Insert virtual student"""
        self.conn.execute("""
            INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            student_data.get("student_id"),
            json.dumps(student_data.get("archive_json", {})),
            json.dumps(student_data.get("simulation_vector", {})),
            json.dumps(student_data.get("sensitive_json", {})),
            student_data.get("identity_fingerprint"),
            json.dumps(student_data.get("llm_generated_fields", {})),
            student_data.get("class_id"),
            student_data.get("assigned_teacher_id"),
            student_data.get("primary_parent_id"),
            student_data.get("seed"),
            student_data.get("created_at")
        ])
    
    def query(self, sql: str):
        """Execute SQL query"""
        return self.conn.execute(sql).fetchall()
    
    def commit(self):
        """Commit changes"""
        self.conn.commit()
