"""
FastAPI server for trade analysis. Run from repo root:
  uvicorn src.api.server:app --reload --host 0.0.0.0 --port 8000
"""
import os
import sys

# Ensure repo root is cwd and src is on path for imports
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
os.chdir(REPO_ROOT)

# Load .env from repo root
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(REPO_ROOT, ".env"))
except ImportError:
    pass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# Import after path is set
from main import run_analysis
from api.serializer import to_json_response

app = FastAPI(
    title="Trade Analyzer API",
    description="Option play analysis: paste a play, get Go/No-Go, Greeks, risk, and recommendation.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_PATH = os.path.join(REPO_ROOT, "config", "config.yaml")


class AnalyzeRequest(BaseModel):
    play: str
    no_ai: bool = False
    no_market: bool = False
    dte_override: Optional[int] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    """Run full analysis on an option play string. Returns JSON result."""
    result = run_analysis(
        play_text=req.play.strip(),
        config_path=CONFIG_PATH,
        no_ai=req.no_ai,
        no_market=req.no_market,
        dte_override=req.dte_override,
        verbose=False,
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Parse failed"))
    return to_json_response(result)
