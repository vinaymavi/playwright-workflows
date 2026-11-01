"""Mock web server for E2E testing of workflows."""

import json
from typing import Dict, Optional, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from threading import Thread
import time


class MockWebAppHandler(BaseHTTPRequestHandler):
    """HTTP request handler for mock web application."""

    # Class-level storage for test data
    test_data: Dict[str, Any] = {
        "valid_credentials": {"username": "testuser", "password": "testpass123"},
        "login_attempts": [],
        "submitted_forms": [],
    }

    def do_GET(self) -> None:
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path == "/":
            self._send_login_page()
        elif path == "/dashboard":
            self._send_dashboard_page()
        elif path == "/health":
            self._send_json({"status": "ok"})
        else:
            self._send_404()

    def do_POST(self) -> None:
        """Handle POST requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path == "/login":
            self._handle_login()
        elif path == "/submit-form":
            self._handle_form_submission()
        else:
            self._send_404()

    def _handle_login(self) -> None:
        """Handle login form submission."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Try form-encoded data
            body_str = body.decode("utf-8")
            data = {}
            for pair in body_str.split("&"):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    data[key] = value

        username = data.get("username", "")
        password = data.get("password", "")

        # Record attempt
        self.test_data["login_attempts"].append(
            {"username": username, "password": password, "timestamp": time.time()}
        )

        # Validate credentials
        if (
            username == self.test_data["valid_credentials"]["username"]
            and password == self.test_data["valid_credentials"]["password"]
        ):
            # Successful login
            self._send_json(
                {
                    "status": "success",
                    "message": "Login successful",
                    "redirect": "/dashboard",
                    "session_id": "mock_session_123",
                }
            )
        else:
            # Failed login
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {
                "status": "error",
                "message": "Invalid credentials",
                "error_code": 401,
            }
            self.wfile.write(json.dumps(response).encode("utf-8"))

    def _handle_form_submission(self) -> None:
        """Handle form submission."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            data = {}

        # Record submission
        self.test_data["submitted_forms"].append(
            {"data": data, "timestamp": time.time()}
        )

        # Return success response
        self._send_json(
            {
                "status": "success",
                "message": "Form submitted successfully",
                "form_id": data.get("form_id", "unknown"),
            }
        )

    def _send_login_page(self) -> None:
        """Send login page HTML."""
        html = """
        <html>
        <head>
            <title>Login</title>
        </head>
        <body>
            <h1>Login</h1>
            <form id="login-form">
                <div>
                    <label for="username">Username:</label>
                    <input type="text" id="username" name="username" required>
                </div>
                <div>
                    <label for="password">Password:</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <button type="submit" id="submit-btn">Submit</button>
            </form>
            <script>
                document.getElementById('login-form').onsubmit = async (e) => {
                    e.preventDefault();
                    const username = document.getElementById('username').value;
                    const password = document.getElementById('password').value;
                    
                    const response = await fetch('/login', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({username, password})
                    });
                    
                    const result = await response.json();
                    if (result.status === 'success') {
                        window.location.href = result.redirect;
                    } else {
                        alert(result.message);
                    }
                };
            </script>
        </body>
        </html>
        """
        self._send_html(html)

    def _send_dashboard_page(self) -> None:
        """Send dashboard page (authenticated area)."""
        html = """
        <html>
        <head>
            <title>Dashboard</title>
        </head>
        <body>
            <h1>Dashboard</h1>
            <p>Welcome to your dashboard!</p>
            <div id="user-info">
                <p>Session active</p>
            </div>
        </body>
        </html>
        """
        self._send_html(html)

    def _send_html(self, html: str) -> None:
        """Send HTML response."""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _send_json(self, data: Dict[str, Any]) -> None:
        """Send JSON response."""
        json_str = json.dumps(data)
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(json_str.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(json_str.encode("utf-8"))

    def _send_404(self) -> None:
        """Send 404 response."""
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = {"status": "error", "message": "Not found"}
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def log_message(self, format, *args):
        """Suppress log messages."""
        pass


class MockWebApp:
    """Mock web application server for testing."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        """Initialize mock web app."""
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[Thread] = None
        self._running = False

    def start(self) -> None:
        """Start the mock web app server."""
        if self._running:
            return

        self.server = HTTPServer((self.host, self.port), MockWebAppHandler)
        self._running = True

        def run_server():
            while self._running:
                self.server.handle_request()

        self.thread = Thread(target=run_server, daemon=True)
        self.thread.start()
        time.sleep(0.1)  # Give server time to start

    def stop(self) -> None:
        """Stop the mock web app server."""
        if not self._running:
            return

        self._running = False
        if self.server:
            self.server.shutdown()
        if self.thread:
            self.thread.join(timeout=2)

    @property
    def url(self) -> str:
        """Get the base URL of the mock server."""
        return f"http://{self.host}:{self.port}"

    @property
    def login_url(self) -> str:
        """Get login page URL."""
        return f"{self.url}/"

    @property
    def dashboard_url(self) -> str:
        """Get dashboard URL."""
        return f"{self.url}/dashboard"

    def get_test_data(self) -> Dict[str, Any]:
        """Get test data collected during server operation."""
        return {
            "login_attempts": MockWebAppHandler.test_data["login_attempts"],
            "submitted_forms": MockWebAppHandler.test_data["submitted_forms"],
        }

    def reset_test_data(self) -> None:
        """Reset test data collection."""
        MockWebAppHandler.test_data["login_attempts"] = []
        MockWebAppHandler.test_data["submitted_forms"] = []

    def set_valid_credentials(self, username: str, password: str) -> None:
        """Set valid credentials for login (for testing)."""
        MockWebAppHandler.test_data["valid_credentials"] = {
            "username": username,
            "password": password,
        }


def create_mock_web_app(host: str = "127.0.0.1", port: int = 8000) -> MockWebApp:
    """Factory function to create a mock web app."""
    return MockWebApp(host, port)
