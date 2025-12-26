# =============================================================================
# RealtyAssistant AI Agent - Database Module
# =============================================================================
"""
SQLite database for storing leads and chat sessions.
Uses SQLAlchemy for ORM and async support.
"""

import os
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import json
import logging

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/leads.db")
Base = declarative_base()

# Ensure data directory exists
Path("data").mkdir(parents=True, exist_ok=True)


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
        """Convert lead to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "consent": self.consent,
            "location": self.location,
            "property_category": self.property_category,
            "property_type": self.property_type,
            "bedroom": self.bedroom,
            "project_status": self.project_status,
            "possession": self.possession,
            "budget": self.budget,
            "properties_found": self.properties_found,
            "search_url": self.search_url,
            "qualified": self.qualified
        }


class LeadDatabase:
    """Database handler for leads."""
    
    def __init__(self, database_url: str = DATABASE_URL):
        """Initialize database connection."""
        # Handle SQLite-specific settings
        connect_args = {}
        if database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        
        self.engine = create_engine(
            database_url,
            connect_args=connect_args,
            poolclass=StaticPool if "sqlite" in database_url else None
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        logger.info(f"Database initialized: {database_url}")
    
    def get_session(self) -> Session:
        """Get a database session."""
        return self.SessionLocal()
    
    def create_lead(self, lead_data: Dict[str, Any]) -> Lead:
        """Create a new lead or update existing one by session_id."""
        with self.get_session() as session:
            try:
                # Check if lead with session_id exists
                existing = session.query(Lead).filter(
                    Lead.session_id == lead_data.get("session_id")
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
                    # Create new lead
                    lead = Lead(
                        session_id=lead_data.get("session_id"),
                        name=lead_data.get("name"),
                        phone=lead_data.get("phone"),
                        email=lead_data.get("email"),
                        consent=lead_data.get("consent", False),
                        location=lead_data.get("location"),
                        property_category=lead_data.get("property_category"),
                        property_type=lead_data.get("property_type"),
                        bedroom=lead_data.get("bedroom"),
                        project_status=lead_data.get("project_status"),
                        possession=lead_data.get("possession"),
                        budget=lead_data.get("budget"),
                        properties_found=lead_data.get("properties_found", 0),
                        search_url=lead_data.get("search_url"),
                        qualified=lead_data.get("qualified", False)
                    )
                    session.add(lead)
                    session.commit()
                    session.refresh(lead)
                    logger.info(f"Created lead: {lead.session_id}")
                    return lead
                    
            except Exception as e:
                session.rollback()
                logger.error(f"Error saving lead: {e}")
                raise
    
    def get_lead(self, session_id: str) -> Optional[Lead]:
        """Get a lead by session ID."""
        with self.get_session() as session:
            return session.query(Lead).filter(Lead.session_id == session_id).first()
    
    def get_lead_by_id(self, lead_id: int) -> Optional[Lead]:
        """Get a lead by ID."""
        with self.get_session() as session:
            return session.query(Lead).filter(Lead.id == lead_id).first()
    
    def get_all_leads(
        self,
        qualified_only: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[Lead]:
        """Get all leads with optional filtering."""
        with self.get_session() as session:
            query = session.query(Lead)
            
            if qualified_only:
                query = query.filter(Lead.qualified == True)
            
            leads = query.order_by(Lead.created_at.desc()).offset(offset).limit(limit).all()
            # Convert to dicts while session is open
            return [lead.to_dict() for lead in leads]
    
    def get_leads_count(self, qualified_only: bool = False) -> int:
        """Get total count of leads."""
        with self.get_session() as session:
            query = session.query(Lead)
            if qualified_only:
                query = query.filter(Lead.qualified == True)
            return query.count()
    
    def delete_lead(self, session_id: str) -> bool:
        """Delete a lead by session ID."""
        with self.get_session() as session:
            try:
                lead = session.query(Lead).filter(Lead.session_id == session_id).first()
                if lead:
                    session.delete(lead)
                    session.commit()
                    logger.info(f"Deleted lead: {session_id}")
                    return True
                return False
            except Exception as e:
                session.rollback()
                logger.error(f"Error deleting lead: {e}")
                return False


# Global database instance
_db_instance: Optional[LeadDatabase] = None


def get_database() -> LeadDatabase:
    """Get or create database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = LeadDatabase()
    return _db_instance
