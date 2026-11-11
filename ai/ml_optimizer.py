"""
ML-enhanced CSP optimizer that wraps the base CSP solver with machine learning capabilities
"""
import numpy as np
import os
import pickle
import base64
from typing import List, Dict, Any, Optional
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from .config import AIConfig
from .explainability import ExplainabilityEngine

try:
    from ..csp.csp_solver import CSPSolver
    from ..csp.variable import Variable
    from ..csp.constraint import Constraint
except ImportError:
    # Fallback for when CSP modules are not available
    CSPSolver = None
    Variable = None
    Constraint = None

class MLCSPOptimizer:
    """ML-enhanced CSP optimizer that learns from scheduling patterns"""
    
    def __init__(self, base_solver=None):
        self.base_solver = base_solver
        self.variable_ordering_model = RandomForestClassifier(
            n_estimators=AIConfig.ML_ENSEMBLE_SIZE,
            max_depth=AIConfig.ML_MAX_DEPTH,
            random_state=42
        )
        self.value_ordering_model = RandomForestClassifier(
            n_estimators=AIConfig.ML_ENSEMBLE_SIZE,
            max_depth=AIConfig.ML_MAX_DEPTH,
            random_state=42
        )
        self.scaler = StandardScaler()
        self.is_fitted = False
        self.decision_log = []
        self.explainer = ExplainabilityEngine()
        
    def extract_features(self, variable: Variable, assignment: Any = None) -> np.ndarray:
        """Extract features for ML models"""
        # Basic variable features
        features = {
            'domain_size': len(variable.domain),
            'degree': len([c for c in self.base_solver.constraints 
                          if variable.name in [v.name for v in c.variables]]),
            'is_assigned': variable.assigned,
            'is_teacher': hasattr(variable, 'is_teacher') and variable.is_teacher,
            'is_room': hasattr(variable, 'is_room') and variable.is_room,
            'is_course': hasattr(variable, 'is_course') and variable.is_course,
        }
        
        # Add assignment-specific features if provided
        if assignment is not None:
            features.update({
                'assignment_hour': getattr(assignment, 'hour', 0),
                'is_morning': getattr(assignment, 'is_morning', False),
                'is_afternoon': getattr(assignment, 'is_afternoon', False),
            })
            
        return np.array(list(features.values())).reshape(1, -1)
    
    def select_variable(self, variables: List[Variable]) -> Variable:
        """Select next variable using ML-based MRV heuristic"""
        if not self.is_fitted:
            # Fall back to default MRV if model not trained
            return self.base_solver.mrv_heuristic.select_variable(variables)
            
        # Get features for all variables
        features = np.vstack([self.extract_features(var) for var in variables])
        
        # Predict variable selection probabilities
        probs = self.variable_ordering_model.predict_proba(features)
        
        # Select variable with highest probability
        return variables[np.argmax(probs)]
    
    def order_domain_values(self, variable: Variable, domain: List[Any]) -> List[Any]:
        """Order domain values using ML-based LCV heuristic"""
        if not self.is_fitted or not domain:
            return domain
            
        # Get features for each value in domain
        features = np.vstack([self.extract_features(variable, val) for val in domain])
        
        # Predict value ordering scores
        scores = self.value_ordering_model.predict_proba(features)[:, 1]  # Probability of being a good choice
        
        # Sort domain by scores (descending)
        return [val for _, val in sorted(zip(scores, domain), key=lambda x: -x[0])]
    
    def add_decision_log(self, decision: Dict[str, Any]):
        """Log a decision for later analysis and model training"""
        self.decision_log.append(decision)
    
    def train_models(self, X_vars, y_vars, X_vals, y_vals):
        """Train the ML models on collected data"""
        if len(X_vars) > 0:
            X_vars_scaled = self.scaler.fit_transform(X_vars)
            self.variable_ordering_model.fit(X_vars_scaled, y_vars)
            
        if len(X_vals) > 0:
            X_vals_scaled = self.scaler.fit_transform(X_vals)
            self.value_ordering_model.fit(X_vals_scaled, y_vals)
            
        self.is_fitted = True
        
    def solve(self, *args, **kwargs):
        """Solve the CSP with ML enhancements"""
        # Store original heuristics
        orig_var_heuristic = self.base_solver.mrv_heuristic
        orig_val_heuristic = self.base_solver.lcv_heuristic
        
        try:
            # Replace with ML-based heuristics
            self.base_solver.mrv_heuristic = self
            self.base_solver.lcv_heuristic = self
            
            # Solve using base solver with our ML enhancements
            return self.base_solver.solve(*args, **kwargs)
            
        finally:
            # Restore original heuristics
            self.base_solver.mrv_heuristic = orig_var_heuristic
            self.base_solver.lcv_heuristic = orig_val_heuristic

# Example usage:
# base_solver = CSPSolver(variables, constraints)
# ml_optimizer = MLCSPOptimizer(base_solver)
# solution = ml_optimizer.solve()
