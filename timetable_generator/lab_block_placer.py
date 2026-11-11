"""
Lab Block Placer component for managing consecutive slot assignments for laboratory sessions.

This component handles the placement of lab blocks (2 consecutive time slots) for lab subjects
and integrated courses, ensuring proper scheduling constraints are met.
"""
from typing import List, Dict, Set, Tuple, Optional
from models import Teacher, Subject


class LabBlockPlacer:
    """Handles placement of lab blocks (2 consecutive slots) for laboratory sessions"""
    
    def find_consecutive_slots(
        self,
        days: List[str],
        periods: List[int],
        break_periods: Dict[int, str],
        occupied_slots: Set[Tuple[str, int]]
    ) -> List[Tuple[str, int, int]]:
        """
        Find all available consecutive slot pairs across the timetable.
        
        A valid consecutive slot pair must:
        - Be on the same day
        - Have consecutive period numbers (period2 = period1 + 1)
        - Not have a break period between them
        - Both slots must be unoccupied
        
        Args:
            days: List of day names (e.g., ['Monday', 'Tuesday', ...])
            periods: List of all period numbers including breaks
            break_periods: Dict mapping period number to break name
            occupied_slots: Set of (day, period) tuples that are already occupied
            
        Returns:
            List of (day, period1, period2) tuples representing available consecutive slot pairs
        """
        consecutive_pairs = []
        
        for day in days:
            for i in range(len(periods) - 1):
                period1 = periods[i]
                period2 = periods[i + 1]
                
                # Check if periods are actually consecutive (period2 = period1 + 1)
                if period2 != period1 + 1:
                    continue
                
                # Check if either period is a break
                if period1 in break_periods or period2 in break_periods:
                    continue
                
                # Check if either slot is occupied
                if (day, period1) in occupied_slots or (day, period2) in occupied_slots:
                    continue
                
                # This is a valid consecutive slot pair
                consecutive_pairs.append((day, period1, period2))
        
        return consecutive_pairs
    
    def can_place_lab_block(
        self,
        day: str,
        period1: int,
        period2: int,
        teacher: Optional[Teacher],
        occupied_slots: Set[Tuple[str, int]],
        teacher_assignments: Dict[Tuple[str, int], Set[int]],
        hall: Optional[str] = None,
        room_assignments: Optional[Dict[Tuple[str, int], Set[str]]] = None
    ) -> bool:
        """
        Check if a lab block can be placed at the given location.
        
        Verifies:
        - Both slots are unoccupied
        - Periods are consecutive (period2 = period1 + 1)
        - Teacher is available for both slots (if teacher exists)
        - Teacher is not double-booked in either slot (if teacher exists)
        - Hall/room is not already booked in either slot (if room_assignments provided)
        
        Args:
            day: Day name
            period1: First period number
            period2: Second period number
            teacher: Teacher to assign (can be None for subjects without teachers)
            occupied_slots: Set of (day, period) tuples that are already occupied
            teacher_assignments: Dict mapping (day, period) to set of teacher IDs assigned
            hall: Optional hall name to verify availability
            room_assignments: Optional Dict mapping (day, period) to set of hall names assigned
            
        Returns:
            bool: True if lab block can be placed, False otherwise
        """
        # Check if periods are consecutive
        if period2 != period1 + 1:
            return False
        
        # Check if both slots are unoccupied in current timetable
        if (day, period1) in occupied_slots or (day, period2) in occupied_slots:
            return False
        
        # Check room availability across timetables if room_assignments is provided
        if hall and room_assignments:
            slot1_rooms = room_assignments.get((day, period1), set())
            slot2_rooms = room_assignments.get((day, period2), set())
            if hall in slot1_rooms or hall in slot2_rooms:
                return False
        
        # If no teacher assigned (e.g., NSS, MP subjects), placement is valid
        if teacher is None:
            return True
        
        # Check teacher availability for both slots
        if not teacher.is_available(day, period1) or not teacher.is_available(day, period2):
            return False
        
        # Check if teacher is already assigned to these slots
        slot1_teachers = teacher_assignments.get((day, period1), set())
        slot2_teachers = teacher_assignments.get((day, period2), set())
        
        if teacher.id in slot1_teachers or teacher.id in slot2_teachers:
            return False
        
        return True
    
    def place_lab_block(
        self,
        subject: Subject,
        teacher: Optional[Teacher],
        day: str,
        period1: int,
        period2: int,
        hall: str
    ) -> Tuple[Dict, Dict]:
        """
        Create two timetable entries for a lab block.
        
        Both entries will be marked as part of a lab block with:
        - is_lab_block: True
        - lab_block_position: 1 for first slot, 2 for second slot
        - lab_block_id: Unique identifier linking both slots
        
        Args:
            subject: Subject to assign
            teacher: Teacher to assign (can be None)
            day: Day name
            period1: First period number
            period2: Second period number
            hall: Hall/room name
            
        Returns:
            Tuple of (entry1, entry2) dictionaries for the two consecutive slots
        """
        # Generate unique lab block ID
        lab_block_id = f"lab_block_{day}_{period1}_{period2}"
        
        # Create first entry
        entry1 = {
            'day': day,
            'period': period1,
            'subject_id': subject.id,
            'teacher_id': teacher.id if teacher else None,
            'hall': hall,
            'is_break': False,
            'is_lab_block': True,
            'lab_block_position': 1,
            'lab_block_id': lab_block_id
        }
        
        # Create second entry
        entry2 = {
            'day': day,
            'period': period2,
            'subject_id': subject.id,
            'teacher_id': teacher.id if teacher else None,
            'hall': hall,
            'is_break': False,
            'is_lab_block': True,
            'lab_block_position': 2,
            'lab_block_id': lab_block_id
        }
        
        return entry1, entry2
