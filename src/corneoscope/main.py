from fastapi import FastAPI

from corneoscope.api import health
from corneoscope.api.errors import install_error_handling
from corneoscope.core.config import settings

app = FastAPI(title=settings.APP_NAME)
install_error_handling(app)
app.include_router(health.router)
