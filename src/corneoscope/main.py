import logging

from fastapi import FastAPI

from corneoscope.api import analyze, extract, health
from corneoscope.api.errors import install_error_handling
from corneoscope.core.config import settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)

app = FastAPI(title=settings.APP_NAME)
install_error_handling(app)
app.include_router(health.router)
app.include_router(extract.router)
app.include_router(analyze.router)
