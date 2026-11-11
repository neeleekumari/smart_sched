"""
Constraint classes for CSP
"""
from abc import ABC, abstractmethod
from typing import List, Set, Any, Dict
from dataclasses import dataclass
from .variable import Variable

class Constraint(ABC):
    """Abstract base class for constraints"""
    
    def __init__(self, variables: List[Variable]):
        self.variables = variables
        self.scope = set(var.name for var in variables)
    
    @abstractmethod
    def is_satisfied(self, *variables: Variable) -> bool:
        """Check if constraint is satisfied for given variable assignments"""
        pass
    
    def get_scope(self) -> Set[str]:
        """Get the scope (variable names) of this constraint"""
        return self.scope
    
    def involves_variable(self, variable_name: str) -> bool:
        """Check if constraint involves a specific variable"""
        return variable_name in self.scope

class HardConstraint(Constraint):
    """Hard constraint that must be satisfied"""
    
    def __init__(self, variables: List[Variable], constraint_func=None, name: str = None, check_function=None):
        super().__init__(variables)
        # Support both constraint_func and check_function for backward compatibility
        self.constraint_func = constraint_func or check_function
        self.name = name or f"HardConstraint_{id(self)}"
    
    def is_satisfied(self, *variables: Variable) -> bool:
        """Check if hard constraint is satisfied"""
        if self.constraint_func:
            return self.constraint_func(*variables)
        return True

class SoftConstraint(Constraint):
    """Soft constraint with a penalty value"""
    
    def __init__(self, variables: List[Variable], constraint_func=None, penalty: float = 1.0, name: str = None, check_function=None):
        super().__init__(variables)
        # Support both constraint_func and check_function for backward compatibility
        self.constraint_func = constraint_func or check_function
        self.penalty = penalty
        self.name = name or f"SoftConstraint_{id(self)}"
    
    def is_satisfied(self, *variables: Variable) -> bool:
        """Check if soft constraint is satisfied"""
        if self.constraint_func:
            return self.constraint_func(*variables)
        return True
    
    def get_penalty(self, *variables: Variable) -> float:
        """Get penalty value if constraint is violated"""
        if not self.is_satisfied(*variables):
            return self.penalty
        return 0.0

# Specific constraint types for timetable generation

class NoDoubleBookingConstraint(HardConstraint):
    """No teacher can be assigned to two classes at the same time"""
    
    def __init__(self, teacher_var: Variable, time_slot_var: Variable):
        def no_double_booking(teacher, time_slot):
            # This will be implemented in the timetable context
            return True
        super().__init__([teacher_var, time_slot_var], no_double_booking)
    
class SubjectCreditsConstraint(HardConstraint):
    """Subject must have correct number of weekly classes based on credits"""
    
    def __init__(self, subject_var: Variable, weekly_hours_var: Variable):
        def credits_check(subject, weekly_hours):
            return subject.credits == weekly_hours
        super().__init__([subject_var, weekly_hours_var], credits_check)

class LabHoursConstraint(HardConstraint):
    """Lab subjects must have 4 hours per week in 2-hour blocks"""
    
    def __init__(self, subject_var: Variable, lab_blocks_var: Variable):
        def lab_hours_check(subject, lab_blocks):
            if subject.is_lab:
                return lab_blocks == 2  # 2 blocks of 2 hours each
            return True
        super().__init__([subject_var, lab_blocks_var], lab_hours_check)

class NoBackToBackConstraint(SoftConstraint):
    """Avoid same subject back-to-back (soft constraint)"""
    
    def __init__(self, subject1_var: Variable, subject2_var: Variable, time1_var: Variable, time2_var: Variable):
        def no_back_to_back(subject1, subject2, time1, time2):
            if subject1 == subject2:
                # Check if times are consecutive
                return abs(time1.period - time2.period) > 1
            return True
        super().__init__([subject1_var, subject2_var, time1_var, time2_var], no_back_to_back, penalty=0.5)

class MorningCoreSubjectsConstraint(SoftConstraint):
    """Prefer core subjects in morning slots (soft constraint)"""
    
    def __init__(self, subject_var: Variable, time_slot_var: Variable):
        def morning_preference(subject, time_slot):
            if subject.is_core and time_slot.period <= 3:  # First 3 periods are morning
                return True
            return True  # Not a hard constraint
        super().__init__([subject_var, time_slot_var], morning_preference, penalty=0.3)
