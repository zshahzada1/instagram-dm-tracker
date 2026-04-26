"""FastAPI application for Instagram DM Tracker."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import threads, items, scans, settings, reactor, comments

app = FastAPI(
    title="Instagram DM Tracker API",
    description="Read-only API for tracking media shared in Instagram DM threads",
    version="1.0.0",
)

# Configure CORS for React UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(threads.router)
app.include_router(items.router)
app.include_router(scans.router)
app.include_router(settings.router)
app.include_router(reactor.router)
app.include_router(comments.router)


@app.get("/")
def root():
    """Root endpoint with API information."""
    return {
        "name": "Instagram DM Tracker API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "threads": "/threads",
            "items": "/items",
            "scans": "/scans",
            "settings": "/settings",
            "reactor": "/reactor",
            "comments": "/comments",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
