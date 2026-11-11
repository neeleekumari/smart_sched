"""
CSP Solver with backtracking algorithm
"""
from typing import List, Dict, Any, Optional, Callable
from .variable import Variable
from .domain import Domain
from .constraint import Constraint, HardConstraint, SoftConstraint
from .heuristics import MRVHeuristic, LCVHeuristic, ForwardChecking
import time
import random

class CSPSolver:
    """CSP Solver using backtracking with heuristics"""
    
    def __init__(self, variables: List[Variable], constraints: List[Constraint]):
        self.variables = variables
        self.constraints = constraints
        self.solutions = []
        self.max_solutions = 10  # Limit number of solutions
        self.timeout = 300  # 5 minutes timeout
        
        # Initialize heuristics
        self.mrv_heuristic = MRVHeuristic()
        self.lcv_heuristic = LCVHeuristic(constraints)
        self.forward_checking = ForwardChecking(constraints)
        
        # Statistics
        self.nodes_visited = 0
        self.backtracks = 0
        self.start_time = None
    
    def solve(self, find_all_solutions: bool = False) -> List[Dict[str, Any]]:
        """Solve the CSP using backtracking"""
        self.solutions = []
        self.nodes_visited = 0
        self.backtracks = 0
        self.start_time = time.time()
        
        # Create a copy of variables for solving
        solving_variables = [var for var in self.variables if not var.assigned]
        
        self._backtrack(solving_variables, find_all_solutions)
        
        return self.solutions
    
    def _backtrack(self, unassigned_variables: List[Variable], find_all_solutions: bool):
        """Recursive backtracking algorithm"""
        # Check timeout
        if time.time() - self.start_time > self.timeout:
            return
        
        # Check if we have a complete solution
        if not unassigned_variables:
            solution = {var.name: var.value for var in self.variables if var.assigned}
            self.solutions.append(solution)
            
            if not find_all_solutions or len(self.solutions) >= self.max_solutions:
                return
            return
        
        # Select variable using MRV heuristic
        variable = self.mrv_heuristic.select_variable(unassigned_variables)
        if variable is None:
            return
        
        # Order values using LCV heuristic
        ordered_values = self.lcv_heuristic.order_values(variable, unassigned_variables)
        
        for value in ordered_values:
            self.nodes_visited += 1
            
            # Assign value
            if not variable.assign(value):
                continue
            
            # Check if assignment is consistent with hard constraints
            if self._is_consistent(variable):
                # Forward checking
                if self.forward_checking.check_forward(variable, value, unassigned_variables):
                    # Recursively solve remaining variables
                    remaining_variables = [v for v in unassigned_variables if v.name != variable.name]
                    self._backtrack(remaining_variables, find_all_solutions)
                    
                    # If we found enough solutions and not finding all, return
                    if not find_all_solutions and self.solutions:
                        return
                else:
                    self.backtracks += 1
            
            # Unassign and try next value
            variable.unassign()
        
        self.backtracks += 1
    
    def _is_consistent(self, variable: Variable) -> bool:
        """Check if current assignment is consistent with all hard constraints"""
        for constraint in self.constraints:
            if isinstance(constraint, HardConstraint) and constraint.involves_variable(variable.name):
                # Get all variables involved in this constraint
                constraint_vars = [v for v in self.variables if v.name in constraint.get_scope()]
                
                # Check if all variables in constraint are assigned
                if all(var.assigned for var in constraint_vars):
                    if not constraint.is_satisfied(*constraint_vars):
                        return False
        
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get solving statistics"""
        return {
            'solutions_found': len(self.solutions),
            'nodes_visited': self.nodes_visited,
            'backtracks': self.backtracks,
            'time_taken': time.time() - self.start_time if self.start_time else 0,
            'timeout_reached': time.time() - self.start_time > self.timeout if self.start_time else False
        }
    
    def add_constraint(self, constraint: Constraint):
        """Add a new constraint"""
        self.constraints.append(constraint)
        # Reinitialize heuristics with new constraints
        self.lcv_heuristic = LCVHeuristic(self.constraints)
        self.forward_checking = ForwardChecking(self.constraints)
    
    def remove_constraint(self, constraint: Constraint):
        """Remove a constraint"""
        if constraint in self.constraints:
            self.constraints.remove(constraint)
            # Reinitialize heuristics
            self.lcv_heuristic = LCVHeuristic(self.constraints)
            self.forward_checking = ForwardChecking(self.constraints)
    
    def set_timeout(self, timeout_seconds: int):
        """Set timeout for solving"""
        self.timeout = timeout_seconds
    
    def set_max_solutions(self, max_solutions: int):
        """Set maximum number of solutions to find"""
        self.max_solutions = max_solutions
