"""Allow running the gateway via: python -m agent_harness.gateway."""

import uvicorn

from agent_harness.gateway.app import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
