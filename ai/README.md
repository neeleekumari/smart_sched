# AI-Powered Timetable Scheduler

This module enhances the existing CSP-based timetable generator with machine learning capabilities for adaptive scheduling.

## Components

### 1. ML-Enhanced CSP Optimizer (`ml_optimizer.py`)
- Wraps the base CSP solver with ML-based heuristics
- Implements variable and value ordering using trained models
- Maintains decision logs for explainability

### 2. Explainability Engine (`explainability.py`)
- Tracks and explains scheduling decisions
- Provides human-readable explanations for assignments
- Maintains a decision log for analysis

### 3. Feature Engineering (`features.py`)
- Extracts and processes features from:
  - Time slots
  - Teachers
  - Rooms
  - Courses
- Creates interaction features
- Prepares data for ML training

## Getting Started

1. **Initialize the ML Optimizer**
   ```python
   from csp.csp_solver import CSPSolver
   from ai.ml_optimizer import MLCSPOptimizer
   
   # Initialize base solver
   base_solver = CSPSolver(variables, constraints)
   
   # Create ML-enhanced optimizer
   ml_optimizer = MLCSPOptimizer(base_solver)
   ```

2. **Train the Models**
   ```python
   # After collecting some training data
   X_vars, y_vars = prepare_variable_ordering_data()
   X_vals, y_vals = prepare_value_ordering_data()
   
   ml_optimizer.train_models(X_vars, y_vars, X_vals, y_vals)
   ```

3. **Generate Explanations**
   ```python
   from ai.explainability import ExplainabilityEngine
   
   explainer = ExplainabilityEngine()
   explanation = explainer.log_decision(
       variable_name="teacher_123",
       value="10:00-11:30",
       constraints_used=["NoDoubleBooking", "RoomCapacity"],
       alternatives=["09:00-10:30", "11:00-12:30"],
       confidence=0.95
   )
   
   print(explanation.get_summary())
   ```

## Data Collection

The system automatically collects the following types of data for ML training:

1. **Variable Ordering Data**
   - Features: Domain size, degree, variable type
   - Labels: Optimal variable selection (0-1)

2. **Value Ordering Data**
   - Features: Time of day, teacher preferences, room features
   - Labels: Value quality score (0-1)

3. **Constraint Satisfaction Data**
   - Constraint types and weights
   - Violation patterns
   - Conflict resolution outcomes

## Model Training

1. **Initial Training**
   - Start with rule-based heuristics
   - Collect training data from initial runs
   - Train ML models on collected data

2. **Online Learning**
   - Continuously collect new data during operation
   - Periodically retrain models
   - A/B test new models against baseline

## Performance Considerations

- **Caching**: Cache feature computations for performance
- **Batch Processing**: Process features in batches for efficiency
- **Incremental Updates**: Update models incrementally as new data arrives
- **Model Pruning**: Remove low-impact features to reduce dimensionality

## Next Steps

1. Implement reinforcement learning for adaptive constraint weights
2. Add more sophisticated feature engineering
3. Develop visualization tools for model interpretability
4. Add support for transfer learning between institutions
