"""
Data management commands
"""
import click
import os
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from sqlalchemy.orm import Session

from models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import Config

engine = create_engine(Config.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

from models import Teacher, Subject
from import_export import DataImporter
from cli.commands.auth import _get_current_user

console = Console()

@click.group()
def data_commands():
    """Data management commands for teachers and subjects"""
    pass

@data_commands.command()
@click.option('--file', '-f', required=True, help='Path to the import file')
@click.option('--type', '-t', type=click.Choice(['teachers', 'subjects']), required=True, help='Type of data to import')
@click.option('--format', type=click.Choice(['excel', 'csv', 'json']), default='excel', help='File format')
def import_data(file: str, type: str, format: str):
    """Import data from Excel, CSV, or JSON files"""
    if not os.path.exists(file):
        console.print(Panel.fit(
            f"[red]✗[/red] File not found: {file}",
            title="Import Failed",
            border_style="red"
        ))
        return
    
    db = SessionLocal()
    try:
        user = _get_current_user(db)
        if not user:
            return
        
        importer = DataImporter(db, user)
        
        # Import based on type and format
        if type == 'teachers':
            if format == 'excel':
                success, errors, teachers = importer.import_teachers_from_excel(file)
            elif format == 'csv':
                success, errors, teachers = importer.import_teachers_from_csv(file)
            else:  # json
                success, errors, teachers = importer.import_teachers_from_json(file)
        elif type == 'subjects':
            if format == 'excel':
                success, errors, subjects = importer.import_subjects_from_excel(file)
            else:  # csv
                success, errors, subjects = importer.import_subjects_from_csv(file)
        
        if success:
            # Save to database
            if type == 'teachers':
                save_success, save_errors = importer.save_imported_data(teachers=teachers)
            elif type == 'subjects':
                save_success, save_errors = importer.save_imported_data(subjects=subjects)
            
            if save_success:
                count = len(teachers) if type == 'teachers' else len(subjects)
                console.print(Panel.fit(
                    f"[green]✓[/green] Successfully imported {count} {type} from {file}",
                    title="Import Successful",
                    border_style="green"
                ))
            else:
                console.print(Panel.fit(
                    f"[red]✗[/red] Import failed during database save!\n\n"
                    f"Errors:\n" + "\n".join(f"• {error}" for error in save_errors),
                    title="Import Failed",
                    border_style="red"
                ))
        else:
            console.print(Panel.fit(
                f"[red]✗[/red] Import failed!\n\n"
                f"Errors:\n" + "\n".join(f"• {error}" for error in errors),
                title="Import Failed",
                border_style="red"
            ))
    finally:
        db.close()

@data_commands.command()
@click.option('--type', '-t', type=click.Choice(['teachers', 'subjects']), help='Type of data to list')
def list_data(type: str = None):
    """List all data (teachers, subjects)"""
    db = SessionLocal()
    try:
        user = _get_current_user(db)
        if not user:
            return
        
        if type == 'teachers' or type is None:
            teachers = db.query(Teacher).filter(Teacher.user_id == user.id).all()
            if teachers:
                table = Table(title="Teachers")
                table.add_column("ID", style="cyan")
                table.add_column("Name", style="magenta")
                table.add_column("Email", style="green")
                table.add_column("Phone", style="yellow")
                table.add_column("Max Hours/Day", style="blue")
                table.add_column("Can Teach Labs", style="red")
                
                for teacher in teachers:
                    table.add_row(
                        str(teacher.id),
                        teacher.name,
                        teacher.email or "N/A",
                        teacher.phone or "N/A",
                        str(teacher.max_hours_per_day),
                        "Yes" if teacher.can_teach_labs else "No"
                    )
                console.print(table)
            else:
                console.print(Panel.fit("No teachers found.", title="Teachers"))
        
        if type == 'subjects' or type is None:
            subjects = db.query(Subject).filter(Subject.user_id == user.id).all()
            if subjects:
                table = Table(title="Subjects")
                table.add_column("ID", style="cyan")
                table.add_column("Name", style="magenta")
                table.add_column("Code", style="green")
                table.add_column("Credits", style="yellow")
                table.add_column("Type", style="blue")
                table.add_column("Class Size", style="red")
                table.add_column("Teacher", style="white")
                
                for subject in subjects:
                    teacher_name = subject.teacher.name if subject.teacher else "Unassigned"
                    table.add_row(
                        str(subject.id),
                        subject.name,
                        subject.code,
                        str(subject.credits),
                        subject.subject_type.title(),
                        str(subject.class_size),
                        teacher_name
                    )
                console.print(table)
            else:
                console.print(Panel.fit("No subjects found.", title="Subjects"))
                
    finally:
        db.close()

@data_commands.command()
@click.option('--type', '-t', type=click.Choice(['teachers', 'subjects']), required=True, help='Type of data to add')
def add_data(type: str):
    """Add new data interactively"""
    db = SessionLocal()
    try:
        user = _get_current_user(db)
        if not user:
            return
        
        if type == 'teachers':
            _add_teacher_interactive(db, user)
        elif type == 'subjects':
            _add_subject_interactive(db, user)
            
    finally:
        db.close()

@data_commands.command()
@click.option('--type', '-t', type=click.Choice(['teachers', 'subjects']), required=True, help='Type of data to delete')
@click.option('--id', required=True, type=int, help='ID of the item to delete')
def delete_data(type: str, id: int):
    """Delete data by ID"""
    db = SessionLocal()
    try:
        user = _get_current_user(db)
        if not user:
            return
        
        if type == 'teachers':
            item = db.query(Teacher).filter(Teacher.id == id, Teacher.user_id == user.id).first()
        else:  # subjects
            item = db.query(Subject).filter(Subject.id == id, Subject.user_id == user.id).first()
        
        if not item:
            console.print(Panel.fit(
                f"[red]✗[/red] {type.title()} with ID {id} not found!",
                title="Delete Failed",
                border_style="red"
            ))
            return
        
        if Confirm.ask(f"Are you sure you want to delete {type[:-1]} '{item.name}'?"):
            db.delete(item)
            db.commit()
            console.print(Panel.fit(
                f"[green]✓[/green] {type.title()[:-1]} deleted successfully!",
                title="Delete Successful",
                border_style="green"
            ))
        else:
            console.print("Delete cancelled.")
            
    finally:
        db.close()

@data_commands.command()
def templates():
    """Show import templates and examples"""
    db = SessionLocal()
    try:
        user = _get_current_user(db)
        if not user:
            return
        
        importer = DataImporter(db, user)
        templates = importer.get_import_templates()
        
        for data_type, template in templates.items():
            console.print(Panel.fit(
                f"[bold]Required Columns:[/bold] {', '.join(template['required_columns'])}\n"
                f"[bold]Optional Columns:[/bold] {', '.join(template['optional_columns'])}\n\n"
                f"[bold]Example:[/bold]\n" + 
                "\n".join(f"  {k}: {v}" for k, v in template['example'].items()),
                title=f"{data_type.title()} Import Template",
                border_style="blue"
            ))
            
    finally:
        db.close()

def _add_teacher_interactive(db: Session, user):
    """Add teacher interactively"""
    name = Prompt.ask("Teacher name")
    email = Prompt.ask("Email address")
    phone = Prompt.ask("Phone number (optional)", default="")
    max_hours_per_day = int(Prompt.ask("Max hours per day", default="6"))
    max_hours_per_week = int(Prompt.ask("Max hours per week", default="30"))
    can_teach_labs = Confirm.ask("Can teach labs?", default=False)
    
    teacher = Teacher(
        name=name,
        email=email,
        phone=phone if phone else None,
        max_hours_per_day=max_hours_per_day,
        max_hours_per_week=max_hours_per_week,
        can_teach_labs=can_teach_labs,
        availability={},  # Default availability
        user_id=user.id
    )
    
    db.add(teacher)
    db.commit()
    
    console.print(Panel.fit(
        f"[green]✓[/green] Teacher '{name}' added successfully!",
        title="Teacher Added",
        border_style="green"
    ))

def _add_subject_interactive(db: Session, user):
    """Add subject interactively"""
    name = Prompt.ask("Subject name")
    code = Prompt.ask("Subject code")
    credits = int(Prompt.ask("Credits"))
    subject_type = Prompt.ask("Type (theory/lab)", default="theory")
    description = Prompt.ask("Description (optional)", default="")
    class_size = int(Prompt.ask("Class size", default="30"))
    
    # Show available teachers
    teachers = db.query(Teacher).filter(Teacher.user_id == user.id).all()
    if teachers:
        console.print("Available teachers:")
        for teacher in teachers:
            console.print(f"  {teacher.id}: {teacher.name}")
        teacher_id = int(Prompt.ask("Teacher ID (optional)", default="0"))
        teacher_id = teacher_id if teacher_id > 0 else None
    else:
        teacher_id = None
    
    subject = Subject(
        name=name,
        code=code,
        credits=credits,
        subject_type=subject_type,
        description=description if description else None,
        class_size=class_size,
        teacher_id=teacher_id,
        user_id=user.id
    )
    
    db.add(subject)
    db.commit()
    
    console.print(Panel.fit(
        f"[green]✓[/green] Subject '{name}' added successfully!",
        title="Subject Added",
        border_style="green"
    ))
