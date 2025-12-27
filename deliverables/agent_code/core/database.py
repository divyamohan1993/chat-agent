# =============================================================================
# RealtyAssistant AI Agent - Database Module (Fail-Safe)
# =============================================================================
"""
SQLite database for storing leads and chat sessions.
Includes auto-healing, auto-creation, and fail-safe mechanisms.
"""

import os
import shutil
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import SQLAlchemyError, OperationalError

logger = logging.getLogger(__name__)

# Database setup
DATABASE_DIR = Path("data")
DATABASE_PATH = DATABASE_DIR / "leads.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH}")
Base = declarative_base()


def ensure_data_directory():
    """Ensure the data directory exists."""
    try:
        DATABASE_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Data directory ensured: {DATABASE_DIR}")
    except Exception as e:
        logger.error(f"Failed to create data directory: {e}")
        raise


class Lead(Base):
    """Lead model for storing qualified leads."""
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(50), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Contact info
    name = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    consent = Column(Boolean, default=False)
    
    # Search preferences
    location = Column(String(255), nullable=True)
    property_category = Column(String(100), nullable=True)
    property_type = Column(String(100), nullable=True)
    bedroom = Column(String(50), nullable=True)
    project_status = Column(String(100), nullable=True)
    possession = Column(String(100), nullable=True)
    budget = Column(String(100), nullable=True)
    
    # Search results
    properties_found = Column(Integer, default=0)
    search_url = Column(Text, nullable=True)
    
    # Qualification
    qualified = Column(Boolean, default=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert lead to dictionary with safe handling."""
        try:
            return {
                "id": self.id,
                "session_id": self.session_id or "",
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None,
                "name": self.name or "",
                "phone": self.phone or "",
                "email": self.email or "",
                "consent": bool(self.consent),
                "location": self.location or "",
                "property_category": self.property_category or "",
                "property_type": self.property_type or "",
                "bedroom": self.bedroom or "",
                "project_status": self.project_status or "",
                "possession": self.possession or "",
                "budget": self.budget or "",
                "properties_found": int(self.properties_found or 0),
                "search_url": self.search_url or "",
                "qualified": bool(self.qualified)
            }
        except Exception as e:
            logger.error(f"Error converting lead to dict: {e}")
            return {
                "id": getattr(self, 'id', 0),
                "session_id": getattr(self, 'session_id', 'unknown'),
                "error": str(e)
            }


class LeadDatabase:
    """Fail-safe database handler for leads."""
    
    def __init__(self, database_url: str = DATABASE_URL, max_retries: int = 3):
        """
        Initialize database connection with fail-safe mechanisms.
        
        Args:
            database_url: SQLAlchemy database URL
            max_retries: Maximum attempts to initialize/repair database
        """
        self.database_url = database_url
        self.max_retries = max_retries
        self.engine = None
        self.SessionLocal = None
        self._initialized = False
        self._initializing = False  # Guard against re-entry
        
        # Ensure data directory exists
        ensure_data_directory()
        
        # Initialize with retries
        self._initialize_with_retry()
    
    def _get_db_path(self) -> Optional[Path]:
        """Extract the database file path from the URL."""
        if "sqlite:///" in self.database_url:
            path_str = self.database_url.replace("sqlite:///", "")
            return Path(path_str)
        return None
    
    def _check_database_integrity(self) -> bool:
        """Check if the SQLite database is corrupted."""
        db_path = self._get_db_path()
        if not db_path or not db_path.exists():
            return True  # Will be created fresh
        
        try:
            # Use raw sqlite3 to check integrity
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0] == "ok":
                logger.info("Database integrity check passed")
                return True
            else:
                logger.warning(f"Database integrity check failed: {result}")
                return False
        except Exception as e:
            logger.error(f"Database integrity check error: {e}")
            return False
    
    def _backup_database(self) -> Optional[Path]:
        """Create a backup of the current database before repair."""
        db_path = self._get_db_path()
        if not db_path or not db_path.exists():
            return None
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = db_path.parent / f"{db_path.stem}_backup_{timestamp}{db_path.suffix}"
            shutil.copy2(db_path, backup_path)
            logger.info(f"Database backed up to: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            return None
    
    def _attempt_data_recovery(self) -> List[Dict[str, Any]]:
        """Attempt to recover data from a corrupted database."""
        db_path = self._get_db_path()
        if not db_path or not db_path.exists():
            return []
        
        recovered_data = []
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Try to dump what we can
            try:
                cursor.execute("SELECT * FROM leads")
                columns = [description[0] for description in cursor.description]
                for row in cursor.fetchall():
                    try:
                        lead_dict = dict(zip(columns, row))
                        recovered_data.append(lead_dict)
                    except:
                        continue
                logger.info(f"Recovered {len(recovered_data)} leads from corrupted database")
            except Exception as e:
                logger.warning(f"Could not recover leads table: {e}")
            
            conn.close()
        except Exception as e:
            logger.error(f"Data recovery failed: {e}")
        
        return recovered_data
    
    def _reset_database(self):
        """Delete and recreate the database file."""
        db_path = self._get_db_path()
        if db_path and db_path.exists():
            try:
                # Backup first
                self._backup_database()
                
                # Remove corrupted file
                db_path.unlink()
                logger.info(f"Removed corrupted database: {db_path}")
            except Exception as e:
                logger.error(f"Failed to remove database: {e}")
    
    def _validate_schema(self) -> bool:
        """Validate that the database schema is correct."""
        try:
            inspector = inspect(self.engine)
            
            if "leads" not in inspector.get_table_names():
                logger.warning("leads table does not exist")
                return False
            
            # Check for required columns
            columns = {col['name'] for col in inspector.get_columns('leads')}
            required_columns = {'id', 'session_id', 'name', 'phone', 'email'}
            
            if not required_columns.issubset(columns):
                missing = required_columns - columns
                logger.warning(f"Missing required columns: {missing}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Schema validation error: {e}")
            return False
    
    def _initialize_with_retry(self):
        """Initialize database with retry and auto-healing."""
        # Prevent re-entry during initialization
        if self._initializing:
            return
        self._initializing = True
        
        try:
            self._do_initialize()
        finally:
            self._initializing = False
    
    def _do_initialize(self):
        """Actual initialization logic."""
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Database initialization attempt {attempt + 1}/{self.max_retries}")
                
                # Check integrity before connecting
                if not self._check_database_integrity():
                    logger.warning("Database corrupted, attempting recovery...")
                    recovered_data = self._attempt_data_recovery()
                    self._reset_database()
                    
                    # Will restore recovered data after engine creation
                    self._recovered_data = recovered_data
                else:
                    self._recovered_data = None
                
                # Create engine with SQLite-specific settings
                connect_args = {}
                if "sqlite" in self.database_url:
                    connect_args = {"check_same_thread": False}
                
                self.engine = create_engine(
                    self.database_url,
                    connect_args=connect_args,
                    poolclass=StaticPool if "sqlite" in self.database_url else None,
                    pool_pre_ping=True  # Verify connections before use
                )
                
                # Create all tables
                Base.metadata.create_all(self.engine)
                
                # Validate schema
                if not self._validate_schema():
                    logger.warning("Schema validation failed, recreating tables...")
                    Base.metadata.drop_all(self.engine)
                    Base.metadata.create_all(self.engine)
                
                self.SessionLocal = sessionmaker(bind=self.engine)
                
                # Test connection directly (avoid get_session to prevent recursion)
                test_session = self.SessionLocal()
                try:
                    test_session.execute(text("SELECT 1"))
                finally:
                    test_session.close()
                
                self._initialized = True
                logger.info(f"Database initialized successfully: {self.database_url}")
                
                # Restore recovered data if any (after initialization is complete)
                if getattr(self, '_recovered_data', None):
                    self._restore_recovered_data(self._recovered_data)
                    self._recovered_data = None
                
                return
                
            except Exception as e:
                logger.error(f"Database initialization attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries - 1:
                    # Try resetting the database
                    self._reset_database()
                else:
                    # Final fallback - create in-memory database
                    logger.warning("All attempts failed, falling back to in-memory database")
                    self._create_fallback_database()
    
    def _restore_recovered_data(self, data: List[Dict[str, Any]]):
        """Restore recovered data to the fresh database."""
        if not data:
            return
        
        restored = 0
        for lead_data in data:
            try:
                # Clean up datetime fields
                for field in ['created_at', 'updated_at']:
                    if field in lead_data and lead_data[field]:
                        if isinstance(lead_data[field], str):
                            lead_data[field] = datetime.fromisoformat(lead_data[field].replace('Z', '+00:00'))
                
                self.create_lead(lead_data)
                restored += 1
            except Exception as e:
                logger.warning(f"Failed to restore lead: {e}")
        
        logger.info(f"Restored {restored}/{len(data)} leads after database repair")
    
    def _create_fallback_database(self):
        """Create an in-memory fallback database."""
        try:
            self.database_url = "sqlite:///:memory:"
            self.engine = create_engine(
                self.database_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool
            )
            Base.metadata.create_all(self.engine)
            self.SessionLocal = sessionmaker(bind=self.engine)
            self._initialized = True
            logger.warning("Running with in-memory database - data will not persist!")
        except Exception as e:
            logger.error(f"Failed to create fallback database: {e}")
            raise
    
    def is_healthy(self) -> bool:
        """Check if the database is healthy and operational."""
        if not self._initialized:
            return False
        
        try:
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def get_session(self) -> Session:
        """Get a database session with error handling."""
        # Only try to initialize if not already initializing
        if not self._initialized and not getattr(self, '_initializing', False):
            if not self.SessionLocal:
                self._initialize_with_retry()
        
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized")
        
        return self.SessionLocal()
    
    def create_lead(self, lead_data: Dict[str, Any]) -> Lead:
        """Create a new lead or update existing one by session_id."""
        if not self._initialized:
            self._initialize_with_retry()
        
        with self.get_session() as session:
            try:
                # Ensure session_id exists
                session_id = lead_data.get("session_id")
                if not session_id:
                    session_id = f"auto_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    lead_data["session_id"] = session_id
                
                # Check if lead with session_id exists
                existing = session.query(Lead).filter(
                    Lead.session_id == session_id
                ).first()
                
                if existing:
                    # Update existing lead
                    for key, value in lead_data.items():
                        if hasattr(existing, key) and key != "id":
                            setattr(existing, key, value)
                    existing.updated_at = datetime.utcnow()
                    session.commit()
                    session.refresh(existing)
                    logger.info(f"Updated lead: {existing.session_id}")
                    return existing
                else:
                    # Create new lead with safe defaults
                    lead = Lead(
                        session_id=session_id,
                        name=lead_data.get("name") or "",
                        phone=lead_data.get("phone") or "",
                        email=lead_data.get("email") or "",
                        consent=bool(lead_data.get("consent", False)),
                        location=lead_data.get("location") or "",
                        property_category=lead_data.get("property_category") or "",
                        property_type=lead_data.get("property_type") or "",
                        bedroom=lead_data.get("bedroom") or "",
                        project_status=lead_data.get("project_status") or "",
                        possession=lead_data.get("possession") or "",
                        budget=lead_data.get("budget") or "",
                        properties_found=int(lead_data.get("properties_found", 0) or 0),
                        search_url=lead_data.get("search_url") or "",
                        qualified=bool(lead_data.get("qualified", False))
                    )
                    session.add(lead)
                    session.commit()
                    session.refresh(lead)
                    logger.info(f"Created lead: {lead.session_id}")
                    return lead
                    
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Database error saving lead: {e}")
                
                # Try to reinitialize on serious errors
                if "database is locked" in str(e).lower() or "disk" in str(e).lower():
                    self._initialized = False
                    self._initialize_with_retry()
                
                raise
            except Exception as e:
                session.rollback()
                logger.error(f"Error saving lead: {e}")
                raise
    
    def get_lead(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a lead by session ID with safe handling."""
        if not self._initialized:
            self._initialize_with_retry()
        
        try:
            with self.get_session() as session:
                lead = session.query(Lead).filter(Lead.session_id == session_id).first()
                return lead.to_dict() if lead else None
        except Exception as e:
            logger.error(f"Error getting lead {session_id}: {e}")
            return None
    
    def get_lead_by_id(self, lead_id: int) -> Optional[Dict[str, Any]]:
        """Get a lead by ID with safe handling."""
        if not self._initialized:
            self._initialize_with_retry()
        
        try:
            with self.get_session() as session:
                lead = session.query(Lead).filter(Lead.id == lead_id).first()
                return lead.to_dict() if lead else None
        except Exception as e:
            logger.error(f"Error getting lead by id {lead_id}: {e}")
            return None
    
    def get_all_leads(
        self,
        qualified_only: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get all leads with optional filtering and safe error handling."""
        if not self._initialized:
            self._initialize_with_retry()
        
        try:
            with self.get_session() as session:
                query = session.query(Lead)
                
                if qualified_only:
                    query = query.filter(Lead.qualified == True)
                
                # Safe limits
                limit = min(max(1, limit), 1000)  # Between 1 and 1000
                offset = max(0, offset)
                
                leads = query.order_by(Lead.created_at.desc()).offset(offset).limit(limit).all()
                
                # Convert to dicts with safe handling
                result = []
                for lead in leads:
                    try:
                        result.append(lead.to_dict())
                    except Exception as e:
                        logger.warning(f"Error converting lead: {e}")
                        continue
                
                return result
                
        except Exception as e:
            logger.error(f"Error getting all leads: {e}")
            return []  # Return empty list on error instead of raising
    
    def get_leads_count(self, qualified_only: bool = False) -> int:
        """Get total count of leads with error handling."""
        if not self._initialized:
            self._initialize_with_retry()
        
        try:
            with self.get_session() as session:
                query = session.query(Lead)
                if qualified_only:
                    query = query.filter(Lead.qualified == True)
                return query.count()
        except Exception as e:
            logger.error(f"Error getting leads count: {e}")
            return 0  # Return 0 on error
    
    def delete_lead(self, session_id: str) -> bool:
        """Delete a lead by session ID with error handling."""
        if not self._initialized:
            self._initialize_with_retry()
        
        try:
            with self.get_session() as session:
                lead = session.query(Lead).filter(Lead.session_id == session_id).first()
                if lead:
                    session.delete(lead)
                    session.commit()
                    logger.info(f"Deleted lead: {session_id}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Error deleting lead: {e}")
            return False
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics and health info."""
        stats = {
            "initialized": self._initialized,
            "healthy": False,
            "total_leads": 0,
            "qualified_leads": 0,
            "database_url": self.database_url,
            "is_memory": ":memory:" in self.database_url
        }
        
        try:
            stats["healthy"] = self.is_healthy()
            stats["total_leads"] = self.get_leads_count()
            stats["qualified_leads"] = self.get_leads_count(qualified_only=True)
            
            # Get database file size if file-based
            db_path = self._get_db_path()
            if db_path and db_path.exists():
                stats["file_size_bytes"] = db_path.stat().st_size
                stats["file_path"] = str(db_path)
        except Exception as e:
            stats["error"] = str(e)
        
        return stats


# Global database instance
_db_instance: Optional[LeadDatabase] = None


def get_database() -> LeadDatabase:
    """
    Get or create database instance with fail-safe initialization.
    
    Returns:
        LeadDatabase: A healthy database instance
    """
    global _db_instance
    
    if _db_instance is None:
        logger.info("Creating new database instance...")
        _db_instance = LeadDatabase()
    elif not _db_instance.is_healthy():
        logger.warning("Database unhealthy, reinitializing...")
        _db_instance = LeadDatabase()
    
    return _db_instance


def reset_database_instance():
    """Reset the global database instance (useful for testing)."""
    global _db_instance
    _db_instance = None
    logger.info("Database instance reset")
