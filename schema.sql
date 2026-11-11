-- Minimal SQLite schema for the timetable application
-- This file is optional; SQLAlchemy model create_all() is the canonical source of truth.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    updated_at TEXT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    full_name TEXT,
    is_active INTEGER DEFAULT 1,
    is_admin INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS teachers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    updated_at TEXT,
    name TEXT NOT NULL,
    initials TEXT,
    email TEXT,
    phone TEXT,
    availability TEXT,
    max_hours_per_day INTEGER DEFAULT 6,
    max_hours_per_week INTEGER DEFAULT 30,
    min_hours_per_week INTEGER DEFAULT 16,
    single_timetable_hours INTEGER DEFAULT 8,
    can_teach_labs INTEGER DEFAULT 0,
    max_theory_subjects INTEGER DEFAULT 2,
    max_lab_subjects INTEGER DEFAULT 1,
    user_id INTEGER NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    updated_at TEXT,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    credits INTEGER NOT NULL,
    subject_type TEXT NOT NULL,
    abbreviation TEXT,
    description TEXT,
    class_size INTEGER DEFAULT 30,
    user_id INTEGER NOT NULL,
    teacher_id INTEGER,
    semester TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(teacher_id) REFERENCES teachers(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    updated_at TEXT,
    name TEXT NOT NULL,
    semester TEXT,
    programme TEXT,
    class_strength INTEGER DEFAULT 30,
    lecture_hall TEXT,
    class_teacher_id INTEGER,
    user_id INTEGER NOT NULL,
    FOREIGN KEY(class_teacher_id) REFERENCES teachers(id) ON DELETE SET NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS teacher_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    updated_at TEXT,
    teacher_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    section_id INTEGER,
    is_primary INTEGER DEFAULT 1,
    assigned_hours INTEGER DEFAULT 0,
    user_id INTEGER NOT NULL,
    FOREIGN KEY(teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
    FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE SET NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS timetables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    updated_at TEXT,
    name TEXT NOT NULL,
    description TEXT,
    version INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    days TEXT,
    periods TEXT,
    entries_data TEXT,
    generation_time TEXT,
    total_subjects INTEGER DEFAULT 0,
    total_teachers INTEGER DEFAULT 0,
    total_rooms INTEGER DEFAULT 0,
    section_id INTEGER,
    generation_mode TEXT DEFAULT 'single',
    conflicts_detected INTEGER DEFAULT 0,
    workload_validated INTEGER DEFAULT 0,
    programme_name TEXT,
    term_label TEXT,
    semester TEXT,
    wef_date TEXT,
    class_strength INTEGER,
    logo_data_url TEXT,
    sections_meta TEXT,
    user_id INTEGER NOT NULL,
    FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE SET NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
