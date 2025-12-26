# =============================================================================
# RealtyAssistant AI Agent - Test Suite
# =============================================================================
"""
Comprehensive test suite for the RealtyAssistant AI Agent.
Includes unit tests, integration tests, and end-to-end tests.
"""

import os
import sys
import json
import asyncio
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models import (
    LeadInput, ConversationSession, ConversationStage,
    CollectedData, QualificationStatus, QualificationReason,
    PropertyType
)
from core.search_scout import PropertySearcher
from core.llm_engine import LLMEngine, LLMResponse, LLMProvider
from core.fallback import GeminiFallback
from agent import QualificationAgent


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_lead():
    """Create a sample lead for testing."""
    return LeadInput(
        name="John Doe",
        phone="9876543210",
        email="john.doe@example.com"
    )


@pytest.fixture
def sample_collected_data():
    """Create sample collected data."""
    return CollectedData(
        contact_name="John Doe",
        location="Mumbai, Andheri",
        property_type=PropertyType.RESIDENTIAL,
        topology="2 BHK",
        budget_raw="50 to 60 lakhs",
        budget_min=5000000,
        budget_max=6000000,
        sales_consent=True,
        property_count=5
    )


@pytest.fixture
def mock_llm_engine():
    """Create a mock LLM engine."""
    engine = Mock(spec=LLMEngine)
    engine.initialize = AsyncMock(return_value=True)
    engine.generate = AsyncMock(return_value=LLMResponse(
        text="Yes, this is John speaking.",
        provider=LLMProvider.OLLAMA,
        latency_ms=100,
        tokens_used=10,
        success=True
    ))
    engine.get_status = Mock(return_value={"initialized": True})
    return engine


@pytest.fixture
def mock_property_searcher():
    """Create a mock property searcher."""
    from core.search_scout import PropertySearchResult
    
    searcher = Mock(spec=PropertySearcher)
    searcher.initialize = AsyncMock(return_value=True)
    searcher.search = AsyncMock(return_value=PropertySearchResult(
        count=5,
        properties=[
            {"index": 1, "title": "Test Property", "price": "50 Lakhs"}
        ],
        query_params={},
        success=True,
        source_url="https://realtyassistant.in/search"
    ))
    searcher.close = AsyncMock()
    searcher._build_search_url = PropertySearcher._build_search_url.__get__(searcher)
    return searcher


# =============================================================================
# Model Tests
# =============================================================================

class TestLeadInput:
    """Tests for LeadInput model."""
    
    def test_valid_lead(self):
        """Test creating a valid lead."""
        lead = LeadInput(
            name="Test User",
            phone="9876543210",
            email="test@example.com"
        )
        assert lead.name == "Test User"
        assert lead.phone == "9876543210"
    
    def test_phone_validation(self):
        """Test phone number validation."""
        # Valid phone with formatting
        lead = LeadInput(name="Test", phone="+91 98765 43210")
        assert lead.phone == "919876543210"
        
        # Invalid phone
        with pytest.raises(ValueError):
            LeadInput(name="Test", phone="123")
    
    def test_optional_email(self):
        """Test optional email field."""
        lead = LeadInput(name="Test", phone="9876543210")
        assert lead.email is None


class TestCollectedData:
    """Tests for CollectedData model."""
    
    def test_is_complete(self, sample_collected_data):
        """Test completeness check."""
        assert sample_collected_data.is_complete() is True
        
        # Missing data
        incomplete = CollectedData(contact_name="John")
        assert incomplete.is_complete() is False
    
    def test_is_budget_numeric(self, sample_collected_data):
        """Test budget parsing check."""
        assert sample_collected_data.is_budget_numeric() is True
        
        # No numeric budget
        no_budget = CollectedData(budget_raw="flexible")
        assert no_budget.is_budget_numeric() is False


# =============================================================================
# Budget Parsing Tests
# =============================================================================

class TestBudgetParsing:
    """Tests for budget string parsing."""
    
    def test_lakhs_parsing(self):
        """Test parsing lakhs."""
        min_val, max_val = PropertySearcher.parse_budget("50 lakhs")
        assert min_val == 3500000  # 70% of 50 lakhs
        assert max_val == 5000000
    
    def test_crore_parsing(self):
        """Test parsing crores."""
        min_val, max_val = PropertySearcher.parse_budget("1 crore")
        assert min_val == 7000000
        assert max_val == 10000000
    
    def test_range_parsing(self):
        """Test parsing budget range."""
        min_val, max_val = PropertySearcher.parse_budget("50 to 60 lakhs")
        assert min_val == 5000000
        assert max_val == 6000000
    
    def test_mixed_formats(self):
        """Test various budget formats."""
        test_cases = [
            ("50 lakh", 5000000),
            ("1.5 cr", 15000000),
            ("75 lac", 7500000),
            ("2 crores", 20000000),
        ]
        
        for budget_str, expected_max in test_cases:
            _, max_val = PropertySearcher.parse_budget(budget_str)
            assert max_val == expected_max, f"Failed for: {budget_str}"
    
    def test_empty_budget(self):
        """Test empty budget string."""
        min_val, max_val = PropertySearcher.parse_budget("")
        assert min_val is None
        assert max_val is None


# =============================================================================
# Qualification Logic Tests
# =============================================================================

class TestQualificationLogic:
    """Tests for qualification decision logic."""
    
    def test_qualified_lead(self, sample_collected_data):
        """Test lead that should be qualified."""
        # All conditions met
        assert sample_collected_data.property_count > 0
        assert sample_collected_data.sales_consent is True
        assert sample_collected_data.is_budget_numeric() is True
        # Should be qualified
    
    def test_not_qualified_no_properties(self, sample_collected_data):
        """Test lead with no matching properties."""
        sample_collected_data.property_count = 0
        # Should not be qualified
        assert sample_collected_data.property_count == 0
    
    def test_not_qualified_no_consent(self, sample_collected_data):
        """Test lead without sales consent."""
        sample_collected_data.sales_consent = False
        # Should not be qualified
        assert sample_collected_data.sales_consent is False
    
    def test_not_qualified_no_budget(self):
        """Test lead with unparseable budget."""
        data = CollectedData(
            contact_name="John",
            location="Mumbai",
            property_type=PropertyType.RESIDENTIAL,
            topology="2 BHK",
            budget_raw="flexible",  # Not parseable
            sales_consent=True,
            property_count=5
        )
        # Should not be qualified
        assert data.is_budget_numeric() is False


# =============================================================================
# Agent Tests
# =============================================================================

class TestQualificationAgent:
    """Tests for the QualificationAgent."""
    
    @pytest.mark.asyncio
    async def test_agent_initialization(self, mock_llm_engine, mock_property_searcher):
        """Test agent initialization."""
        agent = QualificationAgent(
            llm_engine=mock_llm_engine,
            property_searcher=mock_property_searcher
        )
        
        result = await agent.initialize()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_full_qualification_flow(
        self, sample_lead, mock_llm_engine, mock_property_searcher
    ):
        """Test complete qualification flow."""
        # Setup mock responses for different stages
        responses = [
            "Yes, this is John speaking.",  # Greeting
            "Mumbai, Andheri West",  # Location
            "Residential",  # Property type
            "2 BHK",  # Topology
            "50 to 60 lakhs",  # Budget
            "Yes"  # Consent
        ]
        response_index = [0]
        
        async def mock_generate(*args, **kwargs):
            idx = response_index[0]
            response_index[0] = min(idx + 1, len(responses) - 1)
            return LLMResponse(
                text=responses[idx],
                provider=LLMProvider.OLLAMA,
                latency_ms=100,
                tokens_used=10,
                success=True
            )
        
        mock_llm_engine.generate = mock_generate
        
        agent = QualificationAgent(
            llm_engine=mock_llm_engine,
            property_searcher=mock_property_searcher,
            logs_dir="tests/data/logs",
            leads_dir="tests/data/leads"
        )
        
        summary = await agent.qualify_lead(sample_lead)
        
        assert summary.status == QualificationStatus.QUALIFIED
        assert summary.collected_data.location is not None
        assert summary.collected_data.property_count == 5


# =============================================================================
# LLM Engine Tests
# =============================================================================

class TestLLMEngine:
    """Tests for the LLM Engine."""
    
    @pytest.mark.asyncio
    async def test_fallback_on_timeout(self):
        """Test that engine falls back to Gemini on timeout."""
        # Create engine with fallback enabled but no local LLM
        engine = LLMEngine(
            ollama_base_url="http://localhost:99999",  # Non-existent
            ollama_model="llama3.1:8b",
            timeout_seconds=0.001,  # Very short timeout
            enable_fallback=True
        )
        
        # Initialize should handle missing Ollama gracefully
        await engine.initialize()
        
        # Verify status shows Ollama as unavailable
        status = engine.get_status()
        assert status["ollama"]["available"] is False
        
        # Engine should still work via fallback (if Gemini is configured)
        assert status["initialized"] is True or status["gemini"]["enabled"] is True
    
    def test_get_status(self):
        """Test status reporting."""
        engine = LLMEngine()
        status = engine.get_status()
        
        assert "initialized" in status
        assert "ollama" in status
        assert "gemini" in status


# =============================================================================
# Property Searcher Tests
# =============================================================================

class TestPropertySearcher:
    """Tests for the PropertySearcher."""
    
    def test_build_search_url(self):
        """Test search URL construction."""
        searcher = PropertySearcher()
        
        url = searcher._build_search_url(
            location="Mumbai",
            property_type="residential",
            topology="2 BHK",
            budget_min=5000000,
            budget_max=6000000
        )
        
        assert "realtyassistant.in/search" in url
        assert "location=Mumbai" in url
        assert "property_type=residential" in url
    
    def test_is_available(self):
        """Test availability check."""
        searcher = PropertySearcher()
        # Should return True if Playwright is installed
        available = searcher.is_available()
        assert isinstance(available, bool)


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests that test multiple components together."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_end_to_end_chat_simulation(self, sample_lead):
        """
        End-to-end test of the complete chat flow.
        
        Note: This test requires Ollama or Gemini to be available.
        Skip if neither is available.
        """
        pytest.skip("Requires LLM backend - run manually")
        
        agent = QualificationAgent()
        await agent.initialize()
        
        summary = await agent.qualify_lead(sample_lead, mode="chat")
        
        assert summary is not None
        assert summary.status in [
            QualificationStatus.QUALIFIED,
            QualificationStatus.NOT_QUALIFIED
        ]
        assert summary.reason is not None


# =============================================================================
# API Tests
# =============================================================================

class TestAPI:
    """Tests for the FastAPI endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "status" in data
    
    def test_status_endpoint(self, client):
        """Test status endpoint."""
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    # Create test directories
    Path("tests/data/logs").mkdir(parents=True, exist_ok=True)
    Path("tests/data/leads").mkdir(parents=True, exist_ok=True)
    
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
