"""
Authentication commands
"""
import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from sqlalchemy.orm import Session

from models.base import SessionLocal
from auth import AuthManager

console = Console()

@click.group()
def auth_commands():
    """Authentication and user management commands"""
    pass

@auth_commands.command()
@click.option('--username', prompt='Username', help='Username for the new account')
@click.option('--email', prompt='Email', help='Email address for the new account')
@click.option('--password', prompt='Password', hide_input=True, confirmation_prompt=True, help='Password for the new account')
@click.option('--full-name', prompt='Full Name', help='Full name of the user')
def register(username: str, email: str, password: str, full_name: str):
    """Register a new user account"""
    db = SessionLocal()
    try:
        auth_manager = AuthManager(db)
        success, user, errors = auth_manager.register_user(username, email, password, full_name)
        
        if success:
            console.print(Panel.fit(
                f"[green]✓[/green] User registered successfully!\n"
                f"Username: {user.username}\n"
                f"Email: {user.email}\n"
                f"User ID: {user.id}",
                title="Registration Successful",
                border_style="green"
            ))
        else:
            console.print(Panel.fit(
                f"[red]✗[/red] Registration failed!\n\n"
                f"Errors:\n" + "\n".join(f"• {error}" for error in errors),
                title="Registration Failed",
                border_style="red"
            ))
    finally:
        db.close()

@auth_commands.command()
@click.option('--username', prompt='Username/Email', help='Username or email address')
@click.option('--password', prompt='Password', hide_input=True, help='Password')
def login(username: str, password: str):
    """Login to an existing account"""
    db = SessionLocal()
    try:
        auth_manager = AuthManager(db)
        success, user, token = auth_manager.authenticate_user(username, password)
        
        if success:
            # Save token to file for session management
            with open('.auth_token', 'w') as f:
                f.write(token)
            
            console.print(Panel.fit(
                f"[green]✓[/green] Login successful!\n"
                f"Welcome, {user.full_name or user.username}!\n"
                f"User ID: {user.id}\n"
                f"Admin: {'Yes' if user.is_admin else 'No'}",
                title="Login Successful",
                border_style="green"
            ))
        else:
            console.print(Panel.fit(
                "[red]✗[/red] Login failed!\n"
                "Invalid username/email or password.",
                title="Login Failed",
                border_style="red"
            ))
    finally:
        db.close()

@auth_commands.command()
def logout():
    """Logout and clear session"""
    try:
        import os
        if os.path.exists('.auth_token'):
            os.remove('.auth_token')
        console.print(Panel.fit(
            "[green]✓[/green] Logged out successfully!",
            title="Logout",
            border_style="green"
        ))
    except Exception as e:
        console.print(Panel.fit(
            f"[red]✗[/red] Logout failed: {str(e)}",
            title="Logout Failed",
            border_style="red"
        ))

@auth_commands.command()
def profile():
    """View current user profile"""
    db = SessionLocal()
    try:
        user = _get_current_user(db)
        if not user:
            return
        
        console.print(Panel.fit(
            f"Username: {user.username}\n"
            f"Email: {user.email}\n"
            f"Full Name: {user.full_name or 'Not set'}\n"
            f"User ID: {user.id}\n"
            f"Admin: {'Yes' if user.is_admin else 'No'}\n"
            f"Active: {'Yes' if user.is_active else 'No'}\n"
            f"Created: {user.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            title="User Profile",
            border_style="blue"
        ))
    finally:
        db.close()

@auth_commands.command()
@click.option('--current-password', prompt='Current Password', hide_input=True, help='Current password')
@click.option('--new-password', prompt='New Password', hide_input=True, confirmation_prompt=True, help='New password')
def change_password(current_password: str, new_password: str):
    """Change user password"""
    db = SessionLocal()
    try:
        user = _get_current_user(db)
        if not user:
            return
        
        auth_manager = AuthManager(db)
        success, errors = auth_manager.change_password(user, current_password, new_password)
        
        if success:
            console.print(Panel.fit(
                "[green]✓[/green] Password changed successfully!",
                title="Password Change",
                border_style="green"
            ))
        else:
            console.print(Panel.fit(
                f"[red]✗[/red] Password change failed!\n\n"
                f"Errors:\n" + "\n".join(f"• {error}" for error in errors),
                title="Password Change Failed",
                border_style="red"
            ))
    finally:
        db.close()

@auth_commands.command()
@click.option('--username', help='Username to make admin (admin only)')
def make_admin(username: str):
    """Make a user an admin (admin only)"""
    db = SessionLocal()
    try:
        current_user = _get_current_user(db)
        if not current_user or not current_user.is_admin:
            console.print(Panel.fit(
                "[red]✗[/red] Access denied! Admin privileges required.",
                title="Access Denied",
                border_style="red"
            ))
            return
        
        if not username:
            username = Prompt.ask("Username to make admin")
        
        auth_manager = AuthManager(db)
        user = auth_manager.get_user_by_username(username)
        
        if not user:
            console.print(Panel.fit(
                f"[red]✗[/red] User '{username}' not found!",
                title="User Not Found",
                border_style="red"
            ))
            return
        
        success, errors = auth_manager.make_admin(user)
        
        if success:
            console.print(Panel.fit(
                f"[green]✓[/green] User '{username}' is now an admin!",
                title="Admin Privileges Granted",
                border_style="green"
            ))
        else:
            console.print(Panel.fit(
                f"[red]✗[/red] Failed to make user admin!\n\n"
                f"Errors:\n" + "\n".join(f"• {error}" for error in errors),
                title="Admin Grant Failed",
                border_style="red"
            ))
    finally:
        db.close()

def _get_current_user(db: Session):
    """Get current authenticated user"""
    try:
        with open('.auth_token', 'r') as f:
            token = f.read().strip()
        
        auth_manager = AuthManager(db)
        success, user = auth_manager.verify_token(token)
        
        if not success:
            console.print(Panel.fit(
                "[red]✗[/red] Invalid or expired session. Please login again.",
                title="Authentication Required",
                border_style="red"
            ))
            return None
        
        return user
    except FileNotFoundError:
        console.print(Panel.fit(
            "[red]✗[/red] No active session. Please login first.",
            title="Authentication Required",
            border_style="red"
        ))
        return None
    except Exception as e:
        console.print(Panel.fit(
            f"[red]✗[/red] Authentication error: {str(e)}",
            title="Authentication Error",
            border_style="red"
        ))
        return None
