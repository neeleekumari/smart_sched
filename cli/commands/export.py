"""
Export commands for timetables
"""
import click
import os
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from sqlalchemy.orm import Session

from models.base import SessionLocal
from models import Timetable
from import_export import TimetableExporter
from cli.commands.auth import _get_current_user

console = Console()

@click.group()
def export_commands():
    """Export timetable commands"""
    pass

@export_commands.command()
@click.option('--id', required=True, type=int, help='Timetable ID to export')
@click.option('--format', type=click.Choice(['pdf', 'excel', 'png', 'jpg', 'svg']), required=True, help='Export format')
@click.option('--output', '-o', help='Output file path (optional)')
def export(id: int, format: str, output: str = None):
    """Export a timetable to various formats"""
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
                title="Export Failed",
                border_style="red"
            ))
            return
        
        exporter = TimetableExporter(db, user)
        
        console.print(f"Exporting timetable '{timetable.name}' to {format.upper()}...")
        
        try:
            if format == 'pdf':
                file_path = exporter.export_to_pdf(timetable, output)
            elif format == 'excel':
                file_path = exporter.export_to_excel(timetable, output)
            elif format in ['png', 'jpg']:
                file_path = exporter.export_to_image(timetable, output, format)
            elif format == 'svg':
                file_path = exporter.export_to_svg(timetable, output)
            
            console.print(Panel.fit(
                f"[green]✓[/green] Timetable exported successfully!\n"
                f"File: {file_path}",
                title="Export Successful",
                border_style="green"
            ))
            
        except Exception as e:
            console.print(Panel.fit(
                f"[red]✗[/red] Export failed!\n"
                f"Error: {str(e)}",
                title="Export Failed",
                border_style="red"
            ))
            
    finally:
        db.close()

@export_commands.command()
@click.option('--id', required=True, type=int, help='Timetable ID to export')
@click.option('--output-dir', '-d', help='Output directory (optional)')
def export_all(id: int, output_dir: str = None):
    """Export a timetable in all supported formats"""
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
                title="Export Failed",
                border_style="red"
            ))
            return
        
        exporter = TimetableExporter(db, user)
        
        if output_dir:
            exporter.export_dir = output_dir
            os.makedirs(output_dir, exist_ok=True)
        
        console.print(f"Exporting timetable '{timetable.name}' in all formats...")
        
        try:
            exports = exporter.export_all_formats(timetable)
            
            if exports:
                console.print(Panel.fit(
                    f"[green]✓[/green] Timetable exported in {len(exports)} formats!\n\n"
                    + "\n".join(f"• {fmt.upper()}: {path}" for fmt, path in exports.items()),
                    title="Export Successful",
                    border_style="green"
                ))
            else:
                console.print(Panel.fit(
                    "[red]✗[/red] All export attempts failed!",
                    title="Export Failed",
                    border_style="red"
                ))
                
        except Exception as e:
            console.print(Panel.fit(
                f"[red]✗[/red] Export failed!\n"
                f"Error: {str(e)}",
                title="Export Failed",
                border_style="red"
            ))
            
    finally:
        db.close()

@export_commands.command()
def formats():
    """Show supported export formats"""
    console.print(Panel.fit(
        "[bold]Supported Export Formats:[/bold]\n\n"
        "• [cyan]PDF[/cyan] - Professional document format with tables and formatting\n"
        "• [green]Excel[/green] - Spreadsheet format with multiple sheets (timetable, summary, teacher schedule)\n"
        "• [yellow]PNG[/yellow] - High-quality image format for presentations\n"
        "• [blue]JPG[/blue] - Compressed image format for web use\n"
        "• [magenta]SVG[/magenta] - Scalable vector format for web and print\n\n"
        "[bold]Usage Examples:[/bold]\n"
        "• Export single format: [code]export --id 1 --format pdf[/code]\n"
        "• Export all formats: [code]export-all --id 1[/code]\n"
        "• Custom output path: [code]export --id 1 --format excel --output /path/to/file.xlsx[/code]",
        title="Export Formats",
        border_style="blue"
    ))
