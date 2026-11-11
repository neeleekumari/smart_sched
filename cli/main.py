"""
Main CLI application
"""
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from sqlalchemy.orm import Session

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import Config

engine = create_engine(Config.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
from cli.commands import auth_commands, data_commands, timetable_commands, export_commands

console = Console()

@click.group()
@click.version_option(version="1.0.0")
def main():
    """
    AI Timetable Generator - Generate clash-free timetables using Constraint Satisfaction Problem (CSP) with backtracking.
    
    This tool helps educational institutions create optimal timetables by considering:
    - Teacher availability and workload constraints
    - Room capacity and type requirements  
    - Subject credit requirements and lab hour constraints
    - Break periods and lunch times
    - Multiple soft constraints for optimal scheduling
    """
    pass

# Add command groups
main.add_command(auth_commands)
main.add_command(data_commands)
main.add_command(timetable_commands)
main.add_command(export_commands)

@main.command()
def info():
    """Display system information and capabilities"""
    console.print(Panel.fit(
        "[bold blue]AI Timetable Generator[/bold blue]\n\n"
        "[bold]Features:[/bold]\n"
        "• CSP-based timetable generation with backtracking\n"
        "• Support for teachers, subjects, rooms, and time slots\n"
        "• Lab hour constraints (4 hours/week in 2-hour blocks)\n"
        "• Break period management\n"
        "• Multiple export formats (PDF, Excel, SVG, PNG)\n"
        "• Data import from Excel, CSV, and JSON\n"
        "• User authentication and multi-user support\n"
        "• PostgreSQL database integration\n\n"
        "[bold]Algorithms:[/bold]\n"
        "• Minimum Remaining Values (MRV) heuristic\n"
        "• Least Constraining Value (LCV) heuristic\n"
        "• Forward checking for constraint propagation\n"
        "• Backtracking search with timeout support\n\n"
        "[bold]Constraints:[/bold]\n"
        "• Hard constraints: No double booking, room capacity, subject credits\n"
        "• Soft constraints: No back-to-back classes, morning preference\n",
        title="System Information",
        border_style="blue"
    ))

@main.command()
def status():
    """Check system status and database connection"""
    try:
        db = SessionLocal()
        # Test database connection
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db.close()
        
        console.print(Panel.fit(
            "[green]OK[/green] Database connection: [bold green]OK[/bold green]\n"
            "[green]OK[/green] System status: [bold green]Ready[/bold green]",
            title="System Status",
            border_style="green"
        ))
    except Exception as e:
        console.print(Panel.fit(
            f"[red]FAILED[/red] Database connection: [bold red]Failed[/bold red]\n"
            f"[red]FAILED[/red] Error: {str(e)}",
            title="System Status",
            border_style="red"
        ))

@main.command()
def init():
    """Initialize the database and create tables"""
    from models import Base
    
    try:
        console.print("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        console.print(Panel.fit(
            "[green]✓[/green] Database initialized successfully!\n"
            "All tables have been created.",
            title="Database Initialization",
            border_style="green"
        ))
    except Exception as e:
        console.print(Panel.fit(
            f"[red]✗[/red] Database initialization failed!\n"
            f"Error: {str(e)}",
            title="Database Initialization",
            border_style="red"
        ))

if __name__ == "__main__":
    main()
