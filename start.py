#!/usr/bin/env python3
"""
NovaCart AI Customer Support — Quick Start Script

Run this to install dependencies and start the server.
Usage: python start.py [--reingest]
"""

import os
import sys
import subprocess
import argparse


def run(cmd, check=True, **kwargs):
    print(f"\n$ {cmd}")
    return subprocess.run(cmd, shell=True, check=check, **kwargs)


def main():
    parser = argparse.ArgumentParser(description="Start NovaCart AI Customer Support")
    parser.add_argument("--install", action="store_true", help="Install dependencies first")
    parser.add_argument("--reingest", action="store_true", help="Force re-ingest knowledge base")
    parser.add_argument("--port", type=int, default=8000, help="Port to run on (default: 8000)")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.abspath(__file__))

    # ── Detect Virtual Environment Python ──────────────────────────────────
    python_exe = sys.executable
    if sys.platform == "win32":
        venv_py = os.path.join(project_root, "venv", "Scripts", "python.exe")
    else:
        venv_py = os.path.join(project_root, "venv", "bin", "python")

    if os.path.exists(venv_py):
        python_exe = venv_py
        print(f"💡 Using virtual environment: {python_exe}")

    # ── Check .env ──────────────────────────────────────────────────────────
    if not os.path.exists(".env"):
        print("⚠️  .env file not found. Copying from .env.example...")
        if os.path.exists(".env.example"):
            import shutil
            shutil.copy(".env.example", ".env")
            print("✓ Created .env from .env.example")
        else:
            print("❌ No .env.example found. Please create a .env file.")
            sys.exit(1)

    # ── Install Dependencies ─────────────────────────────────────────────────
    if args.install:
        print("\n📦 Installing dependencies...")
        run(f'"{python_exe}" -m pip install -r requirements.txt')
        print("✓ Dependencies installed")

    # ── Set PYTHONPATH ───────────────────────────────────────────────────────
    env = os.environ.copy()
    env["PYTHONPATH"] = project_root

    # ── Start Server ─────────────────────────────────────────────────────────
    print(f"\n🚀 Starting NovaCart AI Customer Support Server on port {args.port}...")
    print("=" * 60)
    print(f"  API:      http://localhost:{args.port}")
    print(f"  Frontend: http://localhost:{args.port}/")
    print(f"  Docs:     http://localhost:{args.port}/docs")
    print("=" * 60)

    cmd = (
        f'"{python_exe}" -m uvicorn backend.main:app '
        f"--host 0.0.0.0 --port {args.port} --reload --log-level info"
    )

    try:
        run(cmd, env=env)
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped")


if __name__ == "__main__":
    main()
