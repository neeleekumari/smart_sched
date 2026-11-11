"""
Timetable generation and management commands
"""
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine

from config import Config
from models import Teacher, Subject, Timetable
from timetable_generator import TimetableGenerator
from cli.commands.auth import _get_current_user

# Create database session
engine = create_engine(Config.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

console = Console()

@click.group()
def timetable_commands():
    """Timetable generation and management commands"""
    pass

@timetable_commands.command()
@click.option('--name', '-n', help='Name for the timetable')
@click.option('--find-multiple', is_flag=True, help='Find multiple solutions')
@click.option('--timeout', type=int, default=300, help='Timeout in seconds')
def generate(name: str = None, find_multiple: bool = False, timeout: int = 300):
    """Generate a new timetable"""
    db = SessionLocal()
    try:
        user = _get_current_user(db)
        if not user:
            return
        
        # Get data
        teachers = db.query(Teacher).filter(Teacher.user_id == user.id).all()
        subjects = db.query(Subject).filter(Subject.user_id == user.id).all()
        
        if not teachers:
            console.print(Panel.fit(
                "[red]✗[/red] No teachers found. Please add teachers first.",
                title="Generation Failed",
                border_style="red"
            ))
            return
        
        if not subjects:
            console.print(Panel.fit(
                "[red]✗[/red] No subjects found. Please add subjects first.",
                title="Generation Failed",
                border_style="red"
            ))
            return
        
        # Show data summary
        console.print(Panel.fit(
            f"Teachers: {len(teachers)}\n"
            f"Subjects: {len(subjects)}\n"
            f"Find Multiple Solutions: {'Yes' if find_multiple else 'No'}\n"
            f"Timeout: {timeout} seconds",
            title="Generation Parameters",
            border_style="blue"
        ))
        
        if not name:
            name = Prompt.ask("Timetable name", default="Generated Timetable")
        
        # Generate timetable
        generator = TimetableGenerator(db, user)
        generator.find_multiple_solutions = find_multiple
        generator.timeout_seconds = timeout
        
        console.print("Generating timetable... This may take a few minutes.")
        
        success, timetable, errors = generator.generate_timetable(
            teachers, subjects, halls=None, timetable_name=name
        )
        
        if success:
            console.print(Panel.fit(
                f"[green]✓[/green] Timetable generated successfully!\n"
                f"Name: {timetable.name}\n"
                f"Version: {timetable.version}\n"
                f"ID: {timetable.id}\n"
                f"Entries: {len(timetable.entries or [])}",
                title="Generation Successful",
                border_style="green"
            ))
        else:
            console.print(Panel.fit(
                f"[red]✗[/red] Timetable generation failed!\n\n"
                f"Errors:\n" + "\n".join(f"• {error}" for error in errors),
                title="Generation Failed",
                border_style="red"
            ))
            
    finally:
        db.close()

@timetable_commands.command()
def list_timetables():
    """List all generated timetables"""
    db = SessionLocal()
    try:
        user = _get_current_user(db)
        if not user:
            return
        
        timetables = db.query(Timetable).filter(Timetable.user_id == user.id).all()
        
        if timetables:
            table = Table(title="Generated Timetables")
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="magenta")
            table.add_column("Version", style="green")
            table.add_column("Generated", style="yellow")
            table.add_column("Entries", style="blue")
            table.add_column("Active", style="red")
            
            for timetable in timetables:
                table.add_row(
                    str(timetable.id),
                    timetable.name,
                    str(timetable.version),
                    timetable.generation_time.strftime('%Y-%m-%d %H:%M') if timetable.generation_time else "N/A",
                    str(len(timetable.entries or [])),
                    "Yes" if timetable.is_active else "No"
                )
            console.print(table)
        else:
            console.print(Panel.fit("No timetables found.", title="Timetables"))
            
    finally:
        db.close()

@timetable_commands.command()
@click.option('--id', required=True, type=int, help='Timetable ID to view')
def view_timetable(id: int):
    """View a specific timetable"""
    db = SessionLocal()
    try:
        user = _get_current_user(db)
        if not user:
            return
        
        timetable = db.query(Timetable).filter(
            Timetable.id == id,
            Timetable.user_id == user.id
        ).first()
        
        if not timetable:
            console.print(Panel.fit(
                f"[red]✗[/red] Timetable with ID {id} not found!",
                title="Timetable Not Found",
                border_style="red"
            ))
            return
        
        # Show timetable info
        console.print(Panel.fit(
            f"Name: {timetable.name}\n"
            f"Version: {timetable.version}\n"
            f"Generated: {timetable.generation_time.strftime('%Y-%m-%d %H:%M:%S') if timetable.generation_time else 'N/A'}\n"
            f"Description: {timetable.description or 'N/A'}\n"
            f"Total Entries: {len(timetable.entries or [])}",
            title="Timetable Information",
            border_style="blue"
        ))
        
        # Create timetable grid
        _display_timetable_grid(timetable)
        
    finally:
        db.close()

@timetable_commands.command()
@click.option('--id', required=True, type=int, help='Timetable ID to regenerate')
def regenerate(id: int):
    """Regenerate an existing timetable"""
    db = SessionLocal()
    try:
        user = _get_current_user(db)
        if not user:
            return
        
        timetable = db.query(Timetable).filter(
            Timetable.id == id,
            Timetable.user_id == user.id
        ).first()
        
        if not timetable:
            console.print(Panel.fit(
                f"[red]✗[/red] Timetable with ID {id} not found!",
                title="Timetable Not Found",
                border_style="red"
            ))
            return
        
        if not Confirm.ask(f"Are you sure you want to regenerate '{timetable.name}'?"):
            console.print("Regeneration cancelled.")
            return
        
        console.print("Regenerating timetable... This may take a few minutes.")
        
        generator = TimetableGenerator(db, user)
        success, new_timetable, errors = generator.regenerate_timetable(id)
        
        if success:
            console.print(Panel.fit(
                f"[green]✓[/green] Timetable regenerated successfully!\n"
                f"Name: {new_timetable.name}\n"
                f"Version: {new_timetable.version}\n"
                f"ID: {new_timetable.id}",
                title="Regeneration Successful",
                border_style="green"
            ))
        else:
            console.print(Panel.fit(
                f"[red]✗[/red] Timetable regeneration failed!\n\n"
                f"Errors:\n" + "\n".join(f"• {error}" for error in errors),
                title="Regeneration Failed",
                border_style="red"
            ))
            
    finally:
        db.close()

@timetable_commands.command()
@click.option('--id', required=True, type=int, help='Timetable ID to delete')
def delete_timetable(id: int):
    """Delete a timetable"""
    db = SessionLocal()
    try:
        user = _get_current_user(db)
        if not user:
            return
        
        timetable = db.query(Timetable).filter(
            Timetable.id == id,
            Timetable.user_id == user.id
        ).first()
        
        if not timetable:
            console.print(Panel.fit(
                f"[red]✗[/red] Timetable with ID {id} not found!",
                title="Timetable Not Found",
                border_style="red"
            ))
            return
        
        if Confirm.ask(f"Are you sure you want to delete '{timetable.name}'?"):
            db.delete(timetable)
            db.commit()
            console.print(Panel.fit(
                f"[green]✓[/green] Timetable '{timetable.name}' deleted successfully!",
                title="Delete Successful",
                border_style="green"
            ))
        else:
            console.print("Delete cancelled.")
            
    finally:
        db.close()

@timetable_commands.command()
@click.option('--id', required=True, type=int, help='Timetable ID to validate')
def validate(id: int):
    """Validate a timetable for constraint violations"""
    db = SessionLocal()
    try:
        user = _get_current_user(db)
        if not user:
            return
        
        timetable = db.query(Timetable).filter(
            Timetable.id == id,
            Timetable.user_id == user.id
        ).first()
        
        if not timetable:
            console.print(Panel.fit(
                f"[red]✗[/red] Timetable with ID {id} not found!",
                title="Timetable Not Found",
                border_style="red"
            ))
            return
        
        # Get associated data for validation
        teachers = db.query(Teacher).filter(Teacher.user_id == user.id).all()
        subjects = db.query(Subject).filter(Subject.user_id == user.id).all()
        
        from timetable_generator.constraints import TimetableValidator
        validator = TimetableValidator()
        
        is_valid, errors = validator.validate_timetable(
            timetable.entries, teachers, subjects, None
        )
        
        if is_valid:
            console.print(Panel.fit(
                "[green]✓[/green] Timetable is valid! No constraint violations found.",
                title="Validation Successful",
                border_style="green"
            ))
        else:
            console.print(Panel.fit(
                f"[red]✗[/red] Timetable validation failed!\n\n"
                f"Constraint Violations:\n" + "\n".join(f"• {error}" for error in errors),
                title="Validation Failed",
                border_style="red"
            ))
            
    finally:
        db.close()

def _display_timetable_grid(timetable):
    """Display timetable as a grid"""
    # Get all unique days and periods
    days = sorted(set(entry.get('day') for entry in timetable.entries))
    periods = sorted(set(entry.get('period') for entry in timetable.entries))
    
    # Create table
    table = Table(title=f"Timetable: {timetable.name}")
    table.add_column("Period", style="cyan")
    for day in days:
        table.add_column(day, style="magenta")
    
    # Fill in the timetable
    for period in periods:
        row = [f"Period {period}"]
        for day in days:
            entry = next((e for e in timetable.entries if e.get('day') == day and e.get('period') == period), None)
            if entry:
                if entry.get('is_break'):
                    cell_text = f"BREAK\n({entry.get('break_type', 'N/A')})"
                else:
                    # Get subject and teacher names
                    subject_name = "Unknown"
                    teacher_name = "Unknown"
                    hall = entry.get('hall') or 'No Hall'
                    
                    # For now, we'll just show the IDs since we don't have the objects loaded
                    cell_text = f"Subject ID: {entry.get('subject_id', 'N/A')}\nTeacher ID: {entry.get('teacher_id', 'N/A')}\n{hall}"
            else:
                cell_text = ""
            row.append(cell_text)
        table.add_row(*row)
    
    console.print(table)
