"""
Command Line Interface for the AI Timetable Generator
"""
from .main import main
from .commands import (
    auth_commands,
    data_commands, 
    timetable_commands,
    export_commands
)

__all__ = [
    'main',
    'auth_commands',
    'data_commands',
    'timetable_commands', 
    'export_commands'
]
