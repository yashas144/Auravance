import asyncio
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.db import init_db


def _ignore_windows_connection_reset(loop: asyncio.AbstractEventLoop) -> None:
    """Silence the Proactor loop's traceback when a client resets a finished connection.

    The request has already been answered by then; asyncio just logs the TCP reset.
    """
    previous = loop.get_exception_handler()

    def handler(event_loop: asyncio.AbstractEventLoop, context: dict) -> None:
        if isinstance(context.get("exception"), ConnectionResetError) and "_call_connection_lost" in repr(
            context.get("handle")
        ):
            return
        if previous is not None:
            previous(event_loop, context)
        else:
            event_loop.default_exception_handler(context)

    loop.set_exception_handler(handler)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if sys.platform == "win32":
        _ignore_windows_connection_reset(asyncio.get_running_loop())
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Auravance backend API for industrial monitoring and predictive maintenance",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()