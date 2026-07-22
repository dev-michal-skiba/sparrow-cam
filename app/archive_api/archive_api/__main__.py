import logging
import os

from archive_api.app import app

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

host = os.environ.get("FLASK_HOST")
if host is None:
    raise RuntimeError("FLASK_HOST environment variable is required")

app.run(host=host, port=5001)
