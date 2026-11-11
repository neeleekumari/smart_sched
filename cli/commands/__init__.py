"""
CLI command modules
"""
from .auth import auth_commands
from .data import data_commands
from .timetable import timetable_commands
from .export import export_commands

__all__ = [
    'auth_commands',
    'data_commands',
    'timetable_commands',
    'export_commands'
]
