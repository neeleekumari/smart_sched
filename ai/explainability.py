"""
Explainable AI components for the timetable scheduler
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import json
from datetime import datetime

@dataclass
class DecisionExplanation:
    """Structured explanation for a scheduling decision"""
    variable_name: str
    value: Any
    confidence: float
    constraints_considered: List[Dict[str, Any]]
    alternatives_considered: List[Any]
    timestamp: str
    reasoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), default=str)
    
    def get_summary(self) -> str:
        """Get a human-readable summary of the explanation"""
        constraints = ", ".join(c['name'] for c in self.constraints_considered[:2])
        if len(self.constraints_considered) > 2:
            constraints += f" and {len(self.constraints_considered) - 2} more"
            
        return (
            f"Assigned {self.variable_name} = {self.value} "
            f"(confidence: {self.confidence:.1%}) "
            f"based on constraints: {constraints}"
        )

class ExplainabilityEngine:
    """Generates and manages explanations for scheduling decisions"""
    
    def __init__(self):
        self.decision_log = []
        self.constraint_descriptions = {
            'NoDoubleBooking': "Ensures no teacher is double-booked",
            'RoomCapacity': "Ensures room capacity is not exceeded",
            'SubjectCredits': "Ensures subject meets required credit hours",
            'LabHours': "Ensures lab sessions are properly scheduled",
            'NoBackToBack': "Avoids scheduling same subject back-to-back",
            'MorningCore': "Prefers core subjects in morning slots"
        }
    
    def _generate_reasoning(self, decision: Dict) -> str:
        """Generate human-readable reasoning for a decision"""
        reasons = []
        if 'constraints' in decision and decision['constraints']:
            reasons.append(f"Respected {len(decision['constraints'])} constraints")
        if 'preferences' in decision:
            reasons.append("Matched user preferences")
        if not reasons:
            reasons.append("Based on available options")
        return ". ".join(reasons) + "."
    
    def log_decision(
        self,
        variable_name: str,
        value: Any,
        constraints_used: List[str],
        alternatives: List[Any],
        confidence: float = 1.0
    ) -> DecisionExplanation:
        """Log a scheduling decision with explanation"""
        reasoning = self._generate_reasoning({
            'variable': variable_name,
            'value': value,
            'constraints': constraints_used,
            'alternatives': alternatives,
            'confidence': confidence
        })
        
        explanation = DecisionExplanation(
            variable_name=variable_name,
            value=value,
            confidence=confidence,
            constraints_considered=[
                {
                    'name': c,
                    'description': self.constraint_descriptions.get(c, "No description available")
                }
                for c in constraints_used
            ],
            alternatives_considered=alternatives,
            timestamp=datetime.utcnow().isoformat(),
            reasoning=reasoning
        )
        
        self.decision_log.append(explanation)
        return explanation
    
    def get_explanation(self, variable_name: str, value: Any = None) -> Optional[DecisionExplanation]:
        """Get explanation for a specific variable assignment"""
        for decision in reversed(self.decision_log):
            if decision.variable_name == variable_name and (value is None or decision.value == value):
                return decision
        return None
    
    def get_decision_chain(self, variable_name: str, depth: int = 3) -> List[DecisionExplanation]:
        """Get chain of decisions leading to a variable assignment"""
        chain = []
        current_var = variable_name
        
        while len(chain) < depth:
            decision = self.get_explanation(current_var)
            if not decision or not decision.constraints_considered:
                break
                
            chain.append(decision)
            
            # Find variables involved in constraints that affected this decision
            constraint_vars = set()
            for constraint in decision.constraints_considered:
                # This is a simplification - in practice, we'd parse constraint scopes
                if 'teacher' in constraint['name'].lower():
                    constraint_vars.add('teacher_id')
                elif 'room' in constraint['name'].lower():
                    constraint_vars.add('room_id')
                    
            # Move to the next variable in the chain
            if constraint_vars:
                current_var = next(iter(constraint_vars))
            else:
                break
                
        return chain
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a summary report of all decisions"""
        return {
            'total_decisions': len(self.decision_log),
            'constraints_used': list(self.constraint_descriptions.keys()),
            'decision_summary': [
                {
                    'variable': d.variable_name,
                    'value': str(d.value),
                    'confidence': d.confidence,
                    'timestamp': d.timestamp
                }
                for d in self.decision_log[-10:]  # Last 10 decisions
            ]
        }
