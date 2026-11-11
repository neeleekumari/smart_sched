#!/usr/bin/env python3
"""
Unified launcher for Smart Sched (AI Timetable Generator)

Usage examples:
  python run_app.py                 # start API on :5000 and frontend on :3000
  python run_app.py --api-only      # only start API
  python run_app.py --frontend-only # only start frontend
  python run_app.py --api-port 8000 --frontend-port 4000

Environment:
  FRONTEND_PORT can override the frontend port if not passed via CLI.
"""
from __future__ import annotations
import argparse
import os
import sys
import threading
import time
from pathlib import Path

# Optionally load .env for FRONTEND_PORT, etc.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Import Flask app
ROOT = Path(__file__).parent
API_DIR = ROOT / 'api'
FRONTEND_DIR = ROOT / 'frontend'
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

# Ensure database is set up before starting API
try:
    sys.path.insert(0, str(ROOT))
    from models import Base
    from sqlalchemy import create_engine
    from config import Config
    
    def setup_database():
        """Create all database tables from SQLAlchemy models."""
        try:
            engine = create_engine(Config.DATABASE_URL, echo=False)
            Base.metadata.create_all(bind=engine)
            return True
        except Exception as e:
            print(f"Database setup error: {e}")
            return False
except Exception as e:
    print(f"Warning: could not import database setup: {e}")
    setup_database = None  # type: ignore

# Import Flask app instance
try:
    # api/app.py defines `app = Flask(__name__)` guarded by if __name__ == '__main__': for running
    from api.app import app as flask_app  # type: ignore
except Exception as e:
    print("Error: failed to import Flask app from api/app.py:", e)
    sys.exit(1)


def run_api(port: int) -> None:
    # Set up DB if available
    if setup_database is not None:
        try:
            setup_database()
        except Exception as e:
            print(f"Warning: setup_database failed: {e}")
    # Start Flask app
    # Start Flask app
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR) # Suppress werkzeug request logs (clean output)
    
    try:
        from flask import cli
        cli.show_server_banner = lambda *x: None
    except ImportError:
        pass

    # Run with reloader if in main thread (unified mode), otherwise disable
    use_reloader = (threading.current_thread() is threading.main_thread())
    
    # Only show message if running (reloader inner process or no reloader)
    if not use_reloader or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        print("\n" + "="*50)
        print(f"  Smart Sched Ready!  (http://localhost:{port})")
        print("="*50 + "\n")

    flask_app.run(debug=True, host='0.0.0.0', port=port, threaded=True, use_reloader=use_reloader)


def run_frontend(port: int) -> None:
    # Serve static files in ./frontend using Python http.server
    import http.server
    import socketserver

    if not FRONTEND_DIR.exists():
        print("Error: frontend directory not found at", FRONTEND_DIR)
        return

    os.chdir(FRONTEND_DIR)

    class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
            super().end_headers()
        def do_OPTIONS(self):
            self.send_response(200)
            self.end_headers()
        def guess_type(self, path):
            mimetype = super().guess_type(path)
            if path.endswith('.js'):
                return 'application/javascript'
            if path.endswith('.css'):
                return 'text/css'
            if path.endswith('.html'):
                return 'text/html'
            return mimetype

    print(f"Starting Frontend server on http://localhost:{port}")
    with socketserver.TCPServer(("", port), CustomHTTPRequestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            httpd.server_close()
            print("Frontend server stopped")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run Smart Sched (API and Frontend)')
    parser.add_argument('--api-only', action='store_true', help='Run only the API server')
    parser.add_argument('--frontend-only', action='store_true', help='Run only the frontend server')
    parser.add_argument('--api-port', type=int, default=5000, help='API port (default: 5000)')
    parser.add_argument('--frontend-port', type=int, default=None, help='Frontend port (default: 3000 or FRONTEND_PORT)')
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Resolve ports - both API and frontend on same port (5000)
    api_port = args.api_port or 5000
    fe_port = args.frontend_port or api_port  # Use same port as API

    if args.api_only and args.frontend_only:
        print("Cannot use --api-only and --frontend-only together")
        sys.exit(2)

    run_api_flag = True
    run_frontend_flag = True
    if args.api_only:
        run_frontend_flag = False
    if args.frontend_only:
        run_api_flag = False

    # If both API and frontend should run, use the unified server (API serves both)
    # If both API and frontend should run, use the unified server (API serves both)
    if run_api_flag and run_frontend_flag:
        run_api(api_port)  # API now serves both frontend and API
        return

    threads: list[threading.Thread] = []

    try:
        if run_api_flag:
            t_api = threading.Thread(target=run_api, args=(api_port,), daemon=True)
            t_api.start()
            threads.append(t_api)
            # small delay to let API come up before starting frontend
            time.sleep(1.5)

        if run_frontend_flag:
            # Frontend runs in main thread to receive KeyboardInterrupt cleanly
            run_frontend(fe_port)
        else:
            # If only API is running, keep main thread alive
            print("API server running. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Threads are daemons; they will exit with main process
        pass


if __name__ == '__main__':
    main()
