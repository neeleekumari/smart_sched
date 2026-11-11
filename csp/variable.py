"""
Variable class for CSP representation
"""
from typing import Any, List, Set
from dataclasses import dataclass

@dataclass
class Variable:
    """Represents a variable in the CSP"""
    name: str
    domain: 'Domain'
    value: Any = None
    assigned: bool = False
    
    def __post_init__(self):
        """Initialize after dataclass creation"""
        if self.domain is None:
            self.domain = Domain([])
    
    def assign(self, value: Any) -> bool:
        """Assign a value to the variable"""
        if value in self.domain.values:
            self.value = value
            self.assigned = True
            return True
        return False
    
    def unassign(self):
        """Unassign the variable"""
        self.value = None
        self.assigned = False
    
    def get_remaining_values(self) -> List[Any]:
        """Get remaining values in domain"""
        return [v for v in self.domain.values if v != self.value]
    
    def is_consistent_with(self, other: 'Variable', constraint: 'Constraint') -> bool:
        """Check if current assignment is consistent with another variable"""
        if not self.assigned or not other.assigned:
            return True
        return constraint.is_satisfied(self, other)
    
    def __repr__(self):
        status = f"={self.value}" if self.assigned else "unassigned"
        return f"Variable({self.name}{status})"
