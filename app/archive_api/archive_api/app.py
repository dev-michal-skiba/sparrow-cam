from flask import Flask

from archive_api.archive import archive_bp
from archive_api.meta import meta_bp

app = Flask(__name__)
app.register_blueprint(archive_bp)
app.register_blueprint(meta_bp)
