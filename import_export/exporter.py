"""
Export functionality for timetables - pixel-perfect from Design Studio
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from io import BytesIO
import base64
import re
import json
import os
import tempfile
from pathlib import Path

from models import Timetable, User, Subject, Teacher


class TimetableExporter:
    """Export timetables in various formats with pixel-perfect styling from Design Studio"""
    
    def __init__(self, db_session: Session, user: User):
        self.db = db_session
        self.user = user

    def _get_maps(self):
        subjects_map = {s.id: s for s in self.db.query(Subject).all()}
        teachers_map = {t.id: t for t in self.db.query(Teacher).all()}
        return subjects_map, teachers_map

    def _get_entry_details(self, entry, subjects_map, teachers_map):
        subject_id = entry.get('subject_id')
        teacher_id = entry.get('teacher_id')
        
        subject_name = subjects_map[subject_id].name if subject_id in subjects_map else 'N/A'
        teacher_name = teachers_map[teacher_id].name if teacher_id in teachers_map else 'N/A'
        room = entry.get('hall') or entry.get('room') or 'N/A'
        
        day = entry.get('day') or entry.get('day_of_week') or ''
        period = entry.get('period') or entry.get('period_number') or ''
        
        return day, period, subject_name, teacher_name, room
    
    def export_from_html(self, html_content: str, format_type: str, css_content: str = None) -> BytesIO:
        """
        Export timetable from HTML content (Design Studio preview) to specified format.
        This ensures pixel-perfect export matching the browser display.
        
        Args:
            html_content: Full HTML of the timetable from Design Studio
            format_type: 'pdf', 'excel', or 'png'
            css_content: Optional CSS styles (can be embedded in HTML)
        
        Returns:
            BytesIO containing the exported file
        """
        if format_type == 'pdf':
            return self._html_to_pdf(html_content, css_content)
        elif format_type == 'png':
            return self._html_to_png(html_content, css_content)
        elif format_type == 'excel':
            # For Excel, we need to parse the HTML and recreate with styling
            return self._html_to_excel(html_content)
        else:
            raise ValueError(f"Unsupported format: {format_type}")
    
    def _html_to_pdf(self, html_content: str, css_content: str = None) -> BytesIO:
        """Convert HTML to PDF using Playwright for pixel-perfect rendering"""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError("Playwright is required. Install: pip install playwright && playwright install chromium")
        
        output = BytesIO()
        
        # Prepare full HTML document with embedded styles
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @page {{
                    size: A4 landscape;
                    margin: 0;
                }}
                body {{
                    margin: 0;
                    padding: 0;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                    -webkit-print-color-adjust: exact;
                    print-color-adjust: exact;
                }}
                * {{
                    box-sizing: border-box;
                }}
                {css_content or ''}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(full_html, wait_until="networkidle")
            
            # Generate PDF
            pdf_bytes = page.pdf(
                format="A4",
                landscape=True,
                print_background=True,
                margin={"top": "1cm", "right": "1cm", "bottom": "1cm", "left": "1cm"}
            )
            output.write(pdf_bytes)
            browser.close()
        
        output.seek(0)
        return output
    
    def _html_to_png(self, html_content: str, css_content: str = None) -> BytesIO:
        """Convert HTML to PNG using Playwright"""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError("Playwright is required. Install: pip install playwright && playwright install chromium")
        
        output = BytesIO()
        
        # Prepare full HTML
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    margin: 0;
                    padding: 20px;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                    background: white;
                    display: inline-block; /* Shrink wrap content */
                }}
                {css_content or ''}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width': 1920, 'height': 1080})
            page.set_content(full_html, wait_until="networkidle")
            
            # Get the bounding box of the body to screenshot only the content
            # We use the body element handle
            body = page.locator("body")
            screenshot = body.screenshot(type='png')
            output.write(screenshot)
            
            browser.close()
        
        output.seek(0)
        return output
    
    def _html_to_excel(self, html_content: str) -> BytesIO:
        """
        Convert HTML table to Excel with preserved styling.
        Parses the HTML and recreates in Excel with colors, fonts, borders, etc.
        """
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
            from openpyxl.utils import get_column_letter
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("openpyxl and beautifulsoup4 required. Install: pip install openpyxl beautifulsoup4")
        
        output = BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.title = "Timetable"
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find the main table - looking for the one with the schedule
        # The Design Studio might have multiple tables, we want the main one
        # Usually it's the one with 'Day / Time' or similar headers
        tables = soup.find_all('table')
        table = None
        for t in tables:
            if t.find('th') and ('Day' in t.text or 'Period' in t.text):
                table = t
                break
        
        if not table and tables:
            table = tables[0] # Fallback to first table
            
        if not table:
            # If no table found, maybe it's a card view or timeline view
            # In that case, we can't easily convert to Excel table structure from HTML
            # We'll create a simple message or try to parse the structure differently
            # For now, let's assume Table View is used for Excel export
            ws['A1'] = "Please switch to Table View in Design Studio for best Excel export results."
            wb.save(output)
            output.seek(0)
            return output
        
        # Helper to convert hex color to RGB
        def hex_to_rgb(hex_color):
            if not hex_color or hex_color == 'transparent':
                return None
            hex_color = hex_color.strip('#')
            if len(hex_color) == 3:
                hex_color = ''.join([c*2 for c in hex_color])
            if len(hex_color) == 6:
                return hex_color.upper()
            return None
        
        # Helper to extract background color from style
        def get_bg_color(element):
            style = element.get('style', '')
            # Look for background or background-color
            bg_match = re.search(r'background(?:-color)?:\s*([^;]+)', style)
            if bg_match:
                color = bg_match.group(1).strip()
                # Handle rgb/rgba
                if color.startswith('rgb'):
                    rgb_match = re.findall(r'\d+', color)
                    if len(rgb_match) >= 3:
                        r, g, b = int(rgb_match[0]), int(rgb_match[1]), int(rgb_match[2])
                        return f"{r:02X}{g:02X}{b:02X}"
                # Handle hex
                elif color.startswith('#'):
                    return hex_to_rgb(color)
                # Handle gradient (take first color)
                elif 'gradient' in color:
                    hex_match = re.search(r'#([0-9a-fA-F]{3,6})', color)
                    if hex_match:
                        return hex_to_rgb(hex_match.group(1))
            return None
        
        # Helper to get text color
        def get_text_color(element):
            style = element.get('style', '')
            color_match = re.search(r'color:\s*([^;]+)', style)
            if color_match:
                color = color_match.group(1).strip()
                if color.startswith('#'):
                    return hex_to_rgb(color)
                elif color.startswith('rgb'):
                    rgb_match = re.findall(r'\d+', color)
                    if len(rgb_match) >= 3:
                        r, g, b = int(rgb_match[0]), int(rgb_match[1]), int(rgb_match[2])
                        return f"{r:02X}{g:02X}{b:02X}"
            return "000000"
        
        # Process table rows
        current_row = 1
        
        # Add metadata if found (Design Studio header)
        header_div = soup.find('div', style=lambda s: s and 'border-radius: 16px 16px 0 0' in s)
        if header_div:
            # Extract text from header
            texts = [p.get_text(strip=True) for p in header_div.find_all(['p', 'h1', 'h2', 'h3'])]
            for text in texts:
                if text:
                    ws.cell(row=current_row, column=1, value=text)
                    current_row += 1
            current_row += 1 # Spacer
        
        # Process the table
        rows = table.find_all('tr')
        
        # Track merged cells to skip them
        # (row, col) -> True
        skip_cells = set()
        
        for r_idx, tr in enumerate(rows):
            excel_row = current_row + r_idx
            current_col = 1
            
            cells = tr.find_all(['th', 'td'])
            
            for cell in cells:
                # Skip cells that are covered by previous rowspans
                while (excel_row, current_col) in skip_cells:
                    current_col += 1
                
                # Get cell content
                # Replace <br> with newline
                for br in cell.find_all('br'):
                    br.replace_with('\n')
                cell_text = cell.get_text(strip=True)
                
                # Get rowspan and colspan
                rowspan = int(cell.get('rowspan', 1))
                colspan = int(cell.get('colspan', 1))
                
                # Write to Excel
                excel_cell = ws.cell(row=excel_row, column=current_col, value=cell_text)
                
                # Apply styling
                bg_color = get_bg_color(cell)
                if bg_color:
                    excel_cell.fill = PatternFill(start_color=bg_color, end_color=bg_color, fill_type='solid')
                
                text_color = get_text_color(cell)
                is_header = cell.name == 'th'
                excel_cell.font = Font(
                    bold=is_header,
                    color=text_color,
                    size=11 if not is_header else 12
                )
                
                excel_cell.alignment = Alignment(
                    horizontal='center',
                    vertical='center',
                    wrap_text=True
                )
                
                excel_cell.border = Border(
                    left=Side(style='thin'),
                    right=Side(style='thin'),
                    top=Side(style='thin'),
                    bottom=Side(style='thin')
                )
                
                # Handle merged cells
                if rowspan > 1 or colspan > 1:
                    end_row = excel_row + rowspan - 1
                    end_col = current_col + colspan - 1
                    ws.merge_cells(
                        start_row=excel_row,
                        start_column=current_col,
                        end_row=end_row,
                        end_column=end_col
                    )
                    
                    # Mark covered cells as skipped
                    for r in range(excel_row, end_row + 1):
                        for c in range(current_col, end_col + 1):
                            if r == excel_row and c == current_col:
                                continue
                            skip_cells.add((r, c))
                
                current_col += colspan
        
        # Auto-adjust column widths
        for col_idx in range(1, ws.max_column + 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = 20
        
        # Set row heights
        for row_idx in range(1, ws.max_row + 1):
            # If it's a data row (not header), make it taller
            if row_idx > current_row: 
                ws.row_dimensions[row_idx].height = 60
            else:
                ws.row_dimensions[row_idx].height = 30
        
        wb.save(output)
        output.seek(0)
        return output

    def export_to_pdf_bytes(self, timetable: Timetable) -> BytesIO:
        """
        Export timetable to PDF format using database data.
        This generates a simple PDF from the timetable entries.
        """
        output = BytesIO()
        
        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            
            # Create PDF
            doc = SimpleDocTemplate(output, pagesize=landscape(A4))
            elements = []
            styles = getSampleStyleSheet()
            
            # Title
            title = Paragraph(f"<b>{timetable.name}</b>", styles['Title'])
            elements.append(title)
            elements.append(Spacer(1, 0.3*inch))
            
            # Get timetable entries
            entries = timetable.entries
            subjects_map, teachers_map = self._get_maps()
            
            if not entries:
                elements.append(Paragraph("No timetable entries found.", styles['Normal']))
            else:
                # Create a simple table
                data = [['Day', 'Period', 'Subject', 'Teacher', 'Room']]
                for entry in entries:
                    day, period, subject_name, teacher_name, room = self._get_entry_details(entry, subjects_map, teachers_map)
                    data.append([
                        day,
                        f"Period {period}",
                        subject_name,
                        teacher_name,
                        room
                    ])
                
                table = Table(data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(table)
            
            doc.build(elements)
            output.seek(0)
            return output
            
        except Exception as e:
            # Fallback: return HTML content
            html_content = self._generate_simple_html(timetable)
            output.write(html_content.encode('utf-8'))
            output.seek(0)
            return output
    
    def export_to_excel_bytes(self, timetable: Timetable) -> BytesIO:
        """
        Export timetable to Excel format using database data.
        """
        output = BytesIO()
        
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment
            
            wb = Workbook()
            ws = wb.active
            ws.title = "Timetable"
            
            # Title
            ws['A1'] = timetable.name
            ws['A1'].font = Font(size=16, bold=True)
            ws.merge_cells('A1:E1')
            
            # Headers
            headers = ['Day', 'Period', 'Subject', 'Teacher', 'Room']
            for col, header in enumerate(headers, start=1):
                cell = ws.cell(row=3, column=col)
                cell.value = header
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
                cell.alignment = Alignment(horizontal='center')
            
            # Data
            entries = timetable.entries
            subjects_map, teachers_map = self._get_maps()
            
            for row, entry in enumerate(entries, start=4):
                day, period, subject_name, teacher_name, room = self._get_entry_details(entry, subjects_map, teachers_map)
                ws.cell(row=row, column=1).value = day
                ws.cell(row=row, column=2).value = f"Period {period}"
                ws.cell(row=row, column=3).value = subject_name
                ws.cell(row=row, column=4).value = teacher_name
                ws.cell(row=row, column=5).value = room
            
            # Auto-adjust column widths
            for col in range(1, 6):
                ws.column_dimensions[chr(64 + col)].width = 20
            
            wb.save(output)
            output.seek(0)
            return output
            
        except ImportError:
            # Fallback to CSV format
            import csv
            from io import StringIO
            
            csv_buffer = StringIO()
            writer = csv.writer(csv_buffer)
            
            # Write title
            writer.writerow([timetable.name])
            writer.writerow([])  # Empty row
            
            # Write headers
            writer.writerow(['Day', 'Period', 'Subject', 'Teacher', 'Room'])
            
            # Write data
            entries = timetable.entries
            subjects_map, teachers_map = self._get_maps()
            
            for entry in entries:
                day, period, subject_name, teacher_name, room = self._get_entry_details(entry, subjects_map, teachers_map)
                writer.writerow([
                    day,
                    f"Period {period}",
                    subject_name,
                    teacher_name,
                    room
                ])
            
            # Convert to bytes
            output.write(csv_buffer.getvalue().encode('utf-8'))
            output.seek(0)
            return output
    
    def export_to_image_bytes(self, timetable: Timetable, format: str = 'png') -> BytesIO:
        """
        Export timetable to image format (PNG/JPG).
        This requires generating HTML first then converting to image.
        """
        output = BytesIO()
        
        try:
            # Try PIL/Pillow first (more likely to be installed)
            from PIL import Image, ImageDraw, ImageFont
            
            # Create a simple image with text
            width, height = 1000, 700
            img = Image.new('RGB', (width, height), color='white')
            draw = ImageDraw.Draw(img)
            
            try:
                font_title = ImageFont.truetype("arial.ttf", 28)
                font_header = ImageFont.truetype("arial.ttf", 16)
                font_text = ImageFont.truetype("arial.ttf", 14)
            except:
                font_title = ImageFont.load_default()
                font_header = ImageFont.load_default()
                font_text = ImageFont.load_default()
            
            # Draw title
            title_bbox = draw.textbbox((0, 0), timetable.name, font=font_title)
            title_width = title_bbox[2] - title_bbox[0]
            draw.text(((width - title_width) // 2, 30), timetable.name, fill='black', font=font_title)
            
            # Draw table headers with background
            y = 100
            header_height = 40
            draw.rectangle([(50, y), (width-50, y+header_height)], fill='#4CAF50')
            draw.text((70, y+10), "Day", fill='white', font=font_header)
            draw.text((220, y+10), "Period", fill='white', font=font_header)
            draw.text((370, y+10), "Subject", fill='white', font=font_header)
            draw.text((570, y+10), "Teacher", fill='white', font=font_header)
            draw.text((770, y+10), "Room", fill='white', font=font_header)
            
            # Draw entries
            y = 150
            row_height = 35
            entries = timetable.entries[:15]
            subjects_map, teachers_map = self._get_maps()
            
            for idx, entry in enumerate(entries):  # Limit to 15 entries
                # Alternate row colors
                if idx % 2 == 0:
                    draw.rectangle([(50, y), (width-50, y+row_height)], fill='#f2f2f2')
                
                day, period, subject_name, teacher_name, room = self._get_entry_details(entry, subjects_map, teachers_map)
                
                draw.text((70, y+8), str(day)[:10], fill='black', font=font_text)
                draw.text((220, y+8), str(period), fill='black', font=font_text)
                draw.text((370, y+8), subject_name[:20], fill='black', font=font_text)
                draw.text((570, y+8), teacher_name[:20], fill='black', font=font_text)
                draw.text((770, y+8), room[:15], fill='black', font=font_text)
                y += row_height
            
            # Save to bytes
            img.save(output, format=format.upper())
            output.seek(0)
            return output
            
        except Exception as e:
            # Fallback: return HTML
            html = self._generate_simple_html(timetable)
            output.write(html.encode('utf-8'))
            output.seek(0)
            return output
    
    def export_to_svg_bytes(self, timetable: Timetable) -> BytesIO:
        """
        Export timetable to SVG format.
        """
        output = BytesIO()
        output.write(b"SVG export not yet implemented")
        output.seek(0)
        return output
    
    def _generate_simple_html(self, timetable: Timetable) -> str:
        """Generate simple HTML representation of timetable"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    padding: 20px; 
                    background: white;
                }}
                h1 {{ 
                    text-align: center; 
                    color: #333;
                    margin-bottom: 30px;
                }}
                table {{ 
                    border-collapse: collapse; 
                    width: 100%; 
                    margin-top: 20px; 
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                th, td {{ 
                    border: 1px solid #ddd; 
                    padding: 12px; 
                    text-align: center; 
                }}
                th {{ 
                    background-color: #4CAF50; 
                    color: white; 
                    font-weight: bold;
                }}
                tr:nth-child(even) {{ 
                    background-color: #f2f2f2; 
                }}
                tr:hover {{
                    background-color: #e8f5e9;
                }}
            </style>
        </head>
        <body>
            <h1>{timetable.name}</h1>
            <table>
                <thead>
                    <tr>
                        <th>Day</th>
                        <th>Period</th>
                        <th>Subject</th>
                        <th>Teacher</th>
                        <th>Room</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        entries = timetable.entries
        subjects_map, teachers_map = self._get_maps()
        
        if not entries:
            html += "<tr><td colspan='5'>No timetable entries found</td></tr>"
        else:
            for entry in entries:
                day, period, subject_name, teacher_name, room = self._get_entry_details(entry, subjects_map, teachers_map)
                html += f"""
                    <tr>
                        <td>{day}</td>
                        <td>Period {period}</td>
                        <td>{subject_name}</td>
                        <td>{teacher_name}</td>
                        <td>{room}</td>
                    </tr>
                """
        
        html += """
                </tbody>
            </table>
        </body>
        </html>
        """
        return html
