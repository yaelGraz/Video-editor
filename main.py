# =============================================================================
# CRITICAL: Force UTF-8 encoding on Windows (prevents charmap codec errors)
# =============================================================================
import os
os.environ['PYTHONUTF8'] = '1'
import sys
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# =============================================================================
# CRITICAL SSL BYPASS: Execute before ANY other imports
# =============================================================================
import ssl
import certifi

# Remove problematic environment variables
for env_var in ['HTTPLIB2_CA_CERTS', 'REQUESTS_CA_BUNDLE', 'SSL_CERT_FILE', 'CURL_CA_BUNDLE']:
    if env_var in os.environ:
        del os.environ[env_var]

# Mock httplib2.certs module to prevent RuntimeError
class MockCerts:
    @staticmethod
    def where():
        return certifi.where()

sys.modules['httplib2.certs'] = MockCerts

# Set certificate paths
_cert_path = certifi.where()
os.environ['SSL_CERT_FILE'] = _cert_path
os.environ['REQUESTS_CA_BUNDLE'] = _cert_path
os.environ['GRPC_SSL_CIPHER_SUITES'] = 'HIGH+ECDSA'
os.environ['GRPC_DEFAULT_SSL_ROOTS_FILE_PATH'] = _cert_path
os.environ['PYTHONHTTPSVERIFY'] = '0'

ssl._create_default_https_context = ssl._create_unverified_context

try:
    import httplib2
    httplib2.CA_CERTS = _cert_path
except ImportError:
    pass

print(f"[SSL] Certificates patched via certifi: {_cert_path}")

# =============================================================================
# Application Setup
# =============================================================================
"""
Video AI Studio - FastAPI Backend
Main entry point. Routes are organized in the routes/ package.
"""
from utils.helpers import setup_ssl_bypass
setup_ssl_bypass()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response
from dotenv import load_dotenv

load_dotenv()

from utils.config import INPUTS_DIR, OUTPUTS_DIR

# Import route modules
from routes.video import router as video_router
from routes.media import router as media_router
from routes.marketing import router as marketing_router
from routes.library import router as library_router
from routes.chat import router as chat_router
from routes.planner import router as planner_router
from routes.publishing import router as publishing_router
from routes.whatsapp import router as whatsapp_router
from routes.effects import router as effects_router
from routes.settings import router as settings_router


# =============================================================================
# App Configuration
# =============================================================================

app = FastAPI(
    title="Video AI Studio",
    description="AI-powered video editing with subtitles, voiceover, and marketing tools",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Length", "Content-Range", "Content-Disposition"],
    max_age=3600,
)


# Middleware: catch Windows ConnectionResetError (WinError 10054)
class CatchConnectionResetMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        try:
            return await call_next(request)
        except ConnectionResetError:
            print(f"[INFO] Client disconnected: {request.method} {request.url.path}")
            return Response(status_code=499)
        except OSError as e:
            if getattr(e, 'winerror', None) == 10054:
                print(f"[INFO] Client disconnected (WinError 10054): {request.method} {request.url.path}")
                return Response(status_code=499)
            raise

app.add_middleware(CatchConnectionResetMiddleware)


# Static files
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")
app.mount("/inputs", StaticFiles(directory=str(INPUTS_DIR)), name="inputs")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")


# =============================================================================
# Register Routers
# =============================================================================

app.include_router(video_router)
app.include_router(media_router)
app.include_router(marketing_router)
app.include_router(library_router)
app.include_router(chat_router)
app.include_router(planner_router)
app.include_router(publishing_router)
app.include_router(whatsapp_router)
app.include_router(effects_router)
app.include_router(settings_router)


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
