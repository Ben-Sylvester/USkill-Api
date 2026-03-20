#!/usr/bin/env python3
"""
Run the USKill background job worker.

Usage:
    python scripts/run_worker.py
    # Or via module:
    python -m app.worker

The worker:
  - Connects to Redis and polls for queued jobs
  - Processes async extraction and batch jobs
  - Updates job progress in the DB
  - Fires webhooks on completion
  - Gracefully handles SIGTERM/SIGINT
"""

import asyncio
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.worker import run_worker

if __name__ == "__main__":
    print("Starting USKill worker...")
    asyncio.run(run_worker())
