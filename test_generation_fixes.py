import sys
import os

sys.path.insert(0, os.path.abspath("."))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import Config
from models import Base, Teacher, Subject, Section, User, Timetable, TeacherAssignment
from timetable_generator.multi_timetable_generator import MultiTimetableGenerator, WorkloadConfig
from timetable_generator.generator import TimetableGenerator

def run_tests():
    print("=== Running Timetable Generation Verification Tests ===")
    
    # Use in-memory SQLite database
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    # 1. Create a User
    user = User(
        username="test_admin",
        email="admin@test.com",
        hashed_password="hashed_pw_test",
        is_admin=True,
        institute_code="TEST"
    )
    db.add(user)
    db.flush()
    
    # 2. Create Teachers
    t1 = Teacher(name="Dr. Alice Smith", initials="DAS", user_id=user.id, max_hours_per_day=6, max_hours_per_week=30)
    t2 = Teacher(name="Prof. Bob Jones", initials="PBJ", user_id=user.id, max_hours_per_day=6, max_hours_per_week=30)
    t3 = Teacher(name="Dr. Charlie Brown", initials="DCB", user_id=user.id, max_hours_per_day=6, max_hours_per_week=30)
    db.add_all([t1, t2, t3])
    db.flush()
    
    # 3. Create Subjects (including 0-credit IKS, Integrated course, Theory, Lab)
    s_iks = Subject(
        name="Indian Knowledge Systems",
        code="IKS101",
        credits=0,
        subject_type="theory",
        user_id=user.id,
        teacher_id=t1.id
    )
    s_int = Subject(
        name="Data Structures",
        code="CS201",
        credits=4,
        subject_type="integrated",
        user_id=user.id,
        teacher_id=t2.id
    )
    s_math = Subject(
        name="Engineering Mathematics",
        code="MA101",
        credits=3,
        subject_type="theory",
        user_id=user.id,
        teacher_id=t3.id
    )
    s_chem_lab = Subject(
        name="Chemistry Lab",
        code="CH102",
        credits=2,
        subject_type="lab",
        user_id=user.id,
        teacher_id=t1.id
    )
    s_phy = Subject(
        name="Physics",
        code="PH101",
        credits=3,
        subject_type="theory",
        user_id=user.id,
        teacher_id=t2.id
    )
    db.add_all([s_iks, s_int, s_math, s_chem_lab, s_phy])
    db.flush()
    
    # 4. Create Sections
    sec_a = Section(name="Section A", lecture_hall="Hall 101", user_id=user.id)
    sec_b = Section(name="Section B", lecture_hall="Hall 102", user_id=user.id)
    db.add_all([sec_a, sec_b])
    db.flush()
    
    teachers = [t1, t2, t3]
    subjects = [s_iks, s_int, s_math, s_chem_lab, s_phy]
    sections = [sec_a, sec_b]
    
    time_config = {
        'days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
        'periods': 6,
        'breaks': [
            {'period': 3, 'name': 'Lunch', 'duration': 45}
        ]
    }
    extra_info = {
        'time_config': time_config,
        'sections': [
            {'name': 'Section A', 'lectureHall': 'Hall 101'},
            {'name': 'Section B', 'lectureHall': 'Hall 102'}
        ]
    }
    
    # 5. Generate Multi-Section Timetable
    multi_gen = MultiTimetableGenerator(db_session=db, user=user)
    success, timetables, errors = multi_gen.generate_multi_timetables(
        teachers=teachers,
        subjects=subjects,
        sections=sections,
        timetable_name="Fall 2026 Test Timetable",
        extra_info=extra_info
    )
    
    print(f"Generation Success: {success}")
    print(f"Errors: {errors}")
    print(f"Timetables Generated: {len(timetables)}")
    assert success, f"Timetable generation failed: {errors}"
    assert len(timetables) == 2, f"Expected 2 timetables, got {len(timetables)}"
    
    # Verify each timetable
    days = time_config['days']
    num_teaching_periods = time_config['periods']
    total_teaching_slots_per_section = len(days) * num_teaching_periods  # 5 * 6 = 30
    
    for idx, tt in enumerate(timetables):
        print(f"\n--- Checking Timetable {idx+1}: {tt.name} ---")
        entries = tt.entries_data
        
        # Check non-break entries count
        teaching_entries = [e for e in entries if not e.get('is_break') and e.get('subject_id') is not None]
        print(f"Total teaching entries: {len(teaching_entries)} / {total_teaching_slots_per_section}")
        assert len(teaching_entries) == total_teaching_slots_per_section, \
            f"Expected {total_teaching_slots_per_section} teaching entries, got {len(teaching_entries)}. Some slots left empty!"
        
        # Check 0-credit subject is scheduled
        iks_entries = [e for e in teaching_entries if e.get('subject_id') == s_iks.id]
        print(f"IKS (0-credit subject) entries: {len(iks_entries)}")
        assert len(iks_entries) >= 1, "0-credit subject 'IKS' was not scheduled!"
        
        # Check integrated subject lab block
        int_lab_entries = [e for e in teaching_entries if e.get('subject_id') == s_int.id and e.get('is_lab_block')]
        print(f"Integrated course lab block entries: {len(int_lab_entries)}")
        assert len(int_lab_entries) == 2, f"Expected 2 lab block entries for integrated course, got {len(int_lab_entries)}"
        
        # Verify lab block entries are consecutive
        lab_entry1, lab_entry2 = int_lab_entries[0], int_lab_entries[1]
        assert lab_entry1['day'] == lab_entry2['day'], "Lab block entries are not on the same day"
        assert abs(lab_entry1['period'] - lab_entry2['period']) == 1, "Lab block entries are not consecutive"
        
        # Check integrated subject theory hours
        int_theory_entries = [e for e in teaching_entries if e.get('subject_id') == s_int.id and not e.get('is_lab_block')]
        print(f"Integrated course theory entries: {len(int_theory_entries)}")
        assert len(int_theory_entries) >= 1, "Integrated course has no theory hours scheduled"
        
        # Check no section period collisions (within this section)
        slot_map = {}
        for e in teaching_entries:
            key = (e['day'], e['period'])
            assert key not in slot_map, f"Section has double booked slot at {key}"
            slot_map[key] = e
            
    # Check cross-section collisions: No teacher double-booked in same (day, period) across sections
    print("\n--- Checking Cross-Section Conflict Prevention ---")
    teacher_schedule = {}  # (day, period, teacher_id) -> list of (timetable_name, subject_id)
    room_schedule = {}     # (day, period, hall) -> list of (timetable_name)
    
    for tt in timetables:
        for e in tt.entries_data:
            if e.get('is_break'):
                continue
            day = e['day']
            period = e['period']
            tid = e.get('teacher_id')
            hall = e.get('hall')
            
            if tid:
                tkey = (day, period, tid)
                if tkey in teacher_schedule:
                    raise AssertionError(f"CONFLICT DETECTED: Teacher {tid} is assigned to multiple classes simultaneously at {day} Period {period}: {teacher_schedule[tkey]} and {tt.name}")
                teacher_schedule[tkey] = (tt.name, e['subject_id'])
                
            if hall:
                rkey = (day, period, hall)
                if rkey in room_schedule:
                    raise AssertionError(f"CONFLICT DETECTED: Lecture Hall '{hall}' is assigned to multiple classes simultaneously at {day} Period {period}: {room_schedule[rkey]} and {tt.name}")
                room_schedule[rkey] = tt.name
                
    print("SUCCESS: Zero teacher conflicts across sections.")
    print("SUCCESS: Zero room conflicts across sections.")
    print("SUCCESS: Zero empty / gap slots remaining.")
    print("SUCCESS: 0-Credit subjects fully reflected in timetables.")
    print("SUCCESS: Integrated course lab & theory constraints satisfied.")
    print("\nALL VERIFICATION CHECKS PASSED!")

if __name__ == "__main__":
    run_tests()
