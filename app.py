# ⬡ Villanyan-Agent 3.0 — Python-only

import uvicorn
from backend.main import create_app

app = create_app()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--reload", action="store_true", help="Auto-reload na zmianach")
    parser.add_argument("--port", type=int, default=7890)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    uvicorn.run(
        "backend.main:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
