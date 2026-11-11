"""
Domain class for CSP variable domains
"""
from typing import List, Any, Set
from dataclasses import dataclass

@dataclass
class Domain:
    """Represents the domain of possible values for a variable"""
    values: List[Any]
    
    def __post_init__(self):
        """Initialize after dataclass creation"""
        if self.values is None:
            self.values = []
        # Remove duplicates while preserving order
        seen = set()
        self.values = [x for x in self.values if not (x in seen or seen.add(x))]
    
    def add_value(self, value: Any):
        """Add a value to the domain"""
        if value not in self.values:
            self.values.append(value)
    
    def remove_value(self, value: Any) -> bool:
        """Remove a value from the domain"""
        if value in self.values:
            self.values.remove(value)
            return True
        return False
    
    def contains(self, value: Any) -> bool:
        """Check if domain contains a value"""
        return value in self.values
    
    def is_empty(self) -> bool:
        """Check if domain is empty"""
        return len(self.values) == 0
    
    def size(self) -> int:
        """Get domain size"""
        return len(self.values)
    
    def copy(self) -> 'Domain':
        """Create a copy of the domain"""
        return Domain(self.values.copy())
    
    def __len__(self):
        return len(self.values)
    
    def __iter__(self):
        return iter(self.values)
    
    def __contains__(self, value):
        return value in self.values
    
    def __repr__(self):
        return f"Domain({self.values})"
