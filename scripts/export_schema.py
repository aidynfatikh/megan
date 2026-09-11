"""Export the authoritative FastAPI schema for frontend type generation."""

import json
from pathlib import Path

from backend.main import app

path = Path(".local/openapi.json")
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(app.openapi(), indent=2))
print(path)
