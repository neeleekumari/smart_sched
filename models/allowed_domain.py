"""
AllowedDomain model for managing teacher email domains
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from .user import Base

class AllowedDomain(Base):
    """Model for storing allowed email domains for teacher verification"""
    __tablename__ = "allowed_domains"
    
    # Base fields
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Domain fields
    domain: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Audit fields
    created_by_user_id = Column(Integer, nullable=True)  # Admin who created this domain
    notes = Column(String(500), nullable=True)  # Optional notes about the domain
    
    def __repr__(self):
        return f"<AllowedDomain(domain='{self.domain}', is_active={self.is_active})>"
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'domain': self.domain,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'notes': self.notes
        }
    
    @staticmethod
    def validate_domain_format(domain: str) -> tuple[bool, str]:
        """
        Validate domain format
        
        Returns:
            (is_valid, error_message)
        """
        if not domain:
            return False, "Domain cannot be empty"
        
        # Remove whitespace
        domain = domain.strip()
        
        # Must start with @
        if not domain.startswith('@'):
            return False, "Domain must start with @"
        
        # Must have at least one dot after @
        if '.' not in domain[1:]:
            return False, "Domain must contain a dot (e.g., @college.ac.in)"
        
        # Check for invalid characters
        allowed_chars = set('abcdefghijklmnopqrstuvwxyz0123456789.-@')
        if not all(c in allowed_chars for c in domain.lower()):
            return False, "Domain contains invalid characters"
        
        # Must not have consecutive dots
        if '..' in domain:
            return False, "Domain cannot have consecutive dots"
        
        # Must not end with dot
        if domain.endswith('.'):
            return False, "Domain cannot end with a dot"
        
        # Must have at least 4 characters (@x.y)
        if len(domain) < 4:
            return False, "Domain is too short"
        
        return True, ""
    
    @staticmethod
    def normalize_domain(domain: str) -> str:
        """
        Normalize domain format
        
        Returns:
            Normalized domain (lowercase, trimmed)
        """
        domain = domain.strip().lower()
        
        # Ensure it starts with @
        if not domain.startswith('@'):
            domain = '@' + domain
        
        return domain
