"""
Heuristics for CSP solving
"""
from typing import List, Any, Dict
from .variable import Variable
from .constraint import Constraint

class MRVHeuristic:
    """Minimum Remaining Values heuristic"""
    
    def select_variable(self, unassigned_variables: List[Variable]) -> Variable:
        """Select variable with minimum remaining values"""
        if not unassigned_variables:
            return None
        
        # Sort by domain size (ascending)
        return min(unassigned_variables, key=lambda var: var.domain.size())

class LCVHeuristic:
    """Least Constraining Value heuristic"""
    
    def __init__(self, constraints: List[Constraint]):
        self.constraints = constraints
    
    def order_values(self, variable: Variable, unassigned_variables: List[Variable]) -> List[Any]:
        """Order values by how many other variables they constrain"""
        value_constraints = {}
        
        for value in variable.domain.values:
            constraint_count = 0
            
            # Temporarily assign the value
            original_value = variable.value
            original_assigned = variable.assigned
            variable.value = value
            variable.assigned = True
            
            # Count how many constraints this assignment affects
            for constraint in self.constraints:
                if constraint.involves_variable(variable.name):
                    for other_var in unassigned_variables:
                        if constraint.involves_variable(other_var.name):
                            # Check if this assignment reduces other variable's domain
                            for other_value in other_var.domain.values:
                                if not constraint.is_satisfied(variable, other_var):
                                    constraint_count += 1
            
            # Restore original state
            variable.value = original_value
            variable.assigned = original_assigned
            
            value_constraints[value] = constraint_count
        
        # Sort by constraint count (ascending - least constraining first)
        return sorted(variable.domain.values, key=lambda v: value_constraints.get(v, 0))

class ForwardChecking:
    """Forward checking for constraint propagation"""
    
    def __init__(self, constraints: List[Constraint]):
        self.constraints = constraints
    
    def check_forward(self, variable: Variable, value: Any, unassigned_variables: List[Variable]) -> bool:
        """Check if assigning value to variable causes any domain to become empty"""
        # Temporarily assign the value
        original_value = variable.value
        original_assigned = variable.assigned
        variable.value = value
        variable.assigned = True
        
        # Check each unassigned variable
        for other_var in unassigned_variables:
            if other_var.name == variable.name:
                continue
            
            # Check if any constraint between these variables would be violated
            for constraint in self.constraints:
                if (constraint.involves_variable(variable.name) and 
                    constraint.involves_variable(other_var.name)):
                    
                    # Check if any value in other_var's domain would violate the constraint
                    valid_values = []
                    for other_value in other_var.domain.values:
                        other_var.value = other_value
                        other_var.assigned = True
                        
                        if constraint.is_satisfied(variable, other_var):
                            valid_values.append(other_value)
                        
                        other_var.value = None
                        other_var.assigned = False
                    
                    # If no valid values remain, forward checking fails
                    if not valid_values:
                        # Restore original state
                        variable.value = original_value
                        variable.assigned = original_assigned
                        return False
        
        # Restore original state
        variable.value = original_value
        variable.assigned = original_assigned
        return True
    
    def reduce_domains(self, variable: Variable, value: Any, unassigned_variables: List[Variable]) -> Dict[str, List[Any]]:
        """Reduce domains of other variables based on current assignment"""
        domain_reductions = {}
        
        # Temporarily assign the value
        original_value = variable.value
        original_assigned = variable.assigned
        variable.value = value
        variable.assigned = True
        
        for other_var in unassigned_variables:
            if other_var.name == variable.name:
                continue
            
            original_domain = other_var.domain.copy()
            valid_values = []
            
            for other_value in other_var.domain.values:
                other_var.value = other_value
                other_var.assigned = True
                
                # Check all constraints involving both variables
                constraint_satisfied = True
                for constraint in self.constraints:
                    if (constraint.involves_variable(variable.name) and 
                        constraint.involves_variable(other_var.name)):
                        if not constraint.is_satisfied(variable, other_var):
                            constraint_satisfied = False
                            break
                
                if constraint_satisfied:
                    valid_values.append(other_value)
                
                other_var.value = None
                other_var.assigned = False
            
            # Store the reduction
            if len(valid_values) < len(original_domain.values):
                domain_reductions[other_var.name] = {
                    'original': original_domain.values,
                    'reduced': valid_values
                }
        
        # Restore original state
        variable.value = original_value
        variable.assigned = original_assigned
        
        return domain_reductions
