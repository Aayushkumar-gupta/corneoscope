from fastapi import FastAPI

from corneoscope.api import health
from corneoscope.core.config import settings

app = FastAPI(title=settings.APP_NAME)
app.include_router(health.router)
