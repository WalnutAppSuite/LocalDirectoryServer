#!/usr/bin/env python3
"""
Simple HTTP Directory Server - JSON API (Simplified & Stable)
Returns directory listings as JSON sorted by modification time.
Includes CORS and HTTPS support.
"""

import os
import sys
import json
import urllib.parse
import subprocess
import time
import logging
from http.server import SimpleHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from io import BytesIO
from datetime import datetime
from pathlib import Path

DEFAULT_PORT = 8000
GOOGLE_DRIVE_PROCESS_NAMES = ["GoogleDriveFS.exe", "GoogleDriveSync.exe", "Google Drive.exe"]
MAX_RETRIES = 10
RETRY_INTERVAL_SECONDS = 60

# Setup logging
LOG_DIR = Path.home() / "directory_server_logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"directory_server_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def is_google_drive_running():
    """Check if Google Drive process is running."""
    try:
        if sys.platform == "win32":
            output = subprocess.check_output(
                ["tasklist", "/FO", "CSV", "/NH"],
                stderr=subprocess.DEVNULL,
                text=True
            )
            for process_name in GOOGLE_DRIVE_PROCESS_NAMES:
                if process_name.lower() in output.lower():
                    return True, process_name
        else:
            try:
                output = subprocess.check_output(
                    ["pgrep", "-f", "-i", "google.*drive"],
                    stderr=subprocess.DEVNULL,
                    text=True
                )
                if output.strip():
                    return True, "Google Drive"
            except subprocess.CalledProcessError:
                pass
            
            try:
                output = subprocess.check_output(
                    ["ps", "aux"],
                    stderr=subprocess.DEVNULL,
                    text=True
                )
                if "google" in output.lower() and "drive" in output.lower():
                    return True, "Google Drive"
            except subprocess.CalledProcessError:
                pass
        
        return False, None
    except Exception as e:
        logger.error(f"Error checking for Google Drive process: {e}")
        return False, None


def wait_for_google_drive():
    """Wait for Google Drive to start, with retries."""
    logger.info("=" * 50)
    logger.info("Directory Server starting...")
    logger.info(f"Log file: {LOG_FILE}")
    logger.info("=" * 50)
    
    for attempt in range(1, MAX_RETRIES + 1):
        is_running, process_name = is_google_drive_running()
        
        if is_running:
            logger.info(f"[OK] Google Drive detected ({process_name}) on attempt {attempt}")
            return True
        
        logger.warning(f"Attempt {attempt}/{MAX_RETRIES}: Google Drive not running")
        
        if attempt < MAX_RETRIES:
            logger.info(f"Waiting {RETRY_INTERVAL_SECONDS} seconds before next check...")
            time.sleep(RETRY_INTERVAL_SECONDS)
    
    logger.error(f"[ERROR] Google Drive not detected after {MAX_RETRIES} attempts")
    logger.error("Exiting without starting server.")
    return False


class DirectoryHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.info("%s - %s" % (self.address_string(), format % args))
    
    def end_headers(self):
        """Add CORS headers and Content-Disposition to every response."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range")
        self.send_header("Access-Control-Max-Age", "86400")
        
        # Check if we should force download for this file path
        path = self.path.split('?')[0]
        _, ext = os.path.splitext(path)
        ext = ext.lower()
        
        # Force download for PowerPoint files (Chrome doesn't handle them well natively)
        force_download_extensions = {'.ppsx', '.pptx', '.ppt', '.pps'}
        
        if ext in force_download_extensions:
            filename = os.path.basename(path)
            # Simple quote handling
            filename = filename.replace('"', '\\"')
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            
        super().end_headers()

    def do_OPTIONS(self):
        """Handle preflight requests."""
        self.send_response(200)
        self.end_headers()

    def guess_type(self, path):
        """
        Override guess_type to return explicit MIME types for Office/PDF files.
        Prevent 'application/octet-stream' which confuses Chrome.
        """
        _, ext = os.path.splitext(path)
        ext = ext.lower()
        
        mime_types = {
            '.ppsx': 'application/vnd.openxmlformats-officedocument.presentationml.slideshow',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.ppt': 'application/vnd.ms-powerpoint',
            '.pps': 'application/vnd.ms-powerpoint',
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel'
        }
        
        if ext in mime_types:
            logger.debug(f"Detected explicit MIME type for {ext}: {mime_types[ext]}")
            return mime_types[ext]
        
        return super().guess_type(path)

    def list_directory(self, path):
        """JSON directory listing."""
        try:
            file_list = os.listdir(path)
        except OSError:
            self.send_error(404, "No permission to list directory")
            return None

        display_path = urllib.parse.unquote(self.path)
        files = []

        for name in file_list:
            fullname = os.path.join(path, name)
            
            try:
                stat_info = os.stat(fullname)
                modified_timestamp = stat_info.st_mtime
                modified_iso = datetime.fromtimestamp(modified_timestamp).isoformat()
                size_bytes = stat_info.st_size
            except OSError:
                modified_timestamp = 0
                modified_iso = None
                size_bytes = 0

            file_type = "file"
            if os.path.isdir(fullname):
                file_type = "directory"
            elif os.path.islink(fullname):
                file_type = "symlink"

            _, extension = os.path.splitext(name)
            extension = extension.lstrip('.').lower() if extension else None

            files.append({
                "name": name,
                "extension": extension,
                "type": file_type,
                "size_bytes": size_bytes,
                "modified_timestamp": modified_timestamp,
                "modified_iso": modified_iso,
                "path": os.path.join(display_path, name).replace("//", "/")
            })

        files.sort(key=lambda x: x["modified_timestamp"], reverse=True)

        response_data = {
            "directory": display_path,
            "total_items": len(files),
            "generated_at": datetime.now().isoformat(),
            "files": files
        }

        content = json.dumps(response_data, indent=2)
        encoded = content.encode('utf-8')
        
        f = BytesIO()
        f.write(encoded)
        length = f.tell()
        f.seek(0)
        
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        return f


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in separate threads for concurrent processing."""
    daemon_threads = True  # Don't wait for threads to finish on shutdown


def run_server(port=DEFAULT_PORT, directory=None, skip_drive_check=False, certfile=None, keyfile=None):
    if not skip_drive_check:
        if not wait_for_google_drive():
            sys.exit(1)

    if directory:
        os.chdir(directory)

    server_address = ('', port)
    httpd = ThreadedHTTPServer(server_address, DirectoryHandler)
    
    # Enable HTTPS if certfile is provided
    protocol = "http"
    if certfile:
        # Clean up paths (remove quotes if passed by shell/batch erroneously)
        certfile = certfile.strip('"').strip("'")
        if keyfile:
            keyfile = keyfile.strip('"').strip("'")
            
        import ssl
        if not keyfile:
            # Assume combined cert/key or key is in certfile
            keyfile = certfile
            
        logger.info(f"Enabling HTTPS using cert: {certfile}")
        
        # Create SSL context
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        try:
            context.load_cert_chain(certfile=certfile, keyfile=keyfile)
            httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
            protocol = "https"
        except Exception as e:
            logger.error(f"Failed to load SSL certificate: {e}")
            sys.exit(1)
    
    logger.info(f"Serving {protocol.upper()} on 0.0.0.0 port {port}")
    logger.info(f"Directory: {os.getcwd()}")
    logger.info(f"Open {protocol}://localhost:{port} in your browser")
    logger.info("Press Ctrl+C to stop the server")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
        httpd.shutdown()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Simple Directory HTTP/HTTPS Server (JSON API)')
    parser.add_argument('-p', '--port', type=int, default=DEFAULT_PORT,
                        help=f'Port to serve on (default: {DEFAULT_PORT})')
    parser.add_argument('-d', '--directory', type=str, default=None,
                        help='Directory to serve (default: current directory)')
    parser.add_argument('--skip-drive-check', action='store_true',
                        help='Skip waiting for Google Drive')
    parser.add_argument('--cert', type=str, default=None,
                        help='Path to SSL certificate file (PEM format) to enable HTTPS')
    parser.add_argument('--key', type=str, default=None,
                        help='Path to SSL private key file (PEM format). Defaults to matching cert file if not specified.')
    args = parser.parse_args()
    
    run_server(
        port=args.port, 
        directory=args.directory, 
        skip_drive_check=args.skip_drive_check,
        certfile=args.cert,
        keyfile=args.key
    )


if __name__ == '__main__':
    main()
