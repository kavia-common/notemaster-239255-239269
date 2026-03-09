from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers.notes import router as notes_router
from src.api.routers.tags import router as tags_router

openapi_tags = [
    {
        "name": "Meta",
        "description": "Health and meta endpoints.",
    },
    {
        "name": "Notes",
        "description": "Create, read, update, delete notes; list and search notes; filter by tag.",
    },
    {
        "name": "Tags",
        "description": "Create, read, update, delete tags; list tags with counts.",
    },
]

app = FastAPI(
    title="NoteMaster API",
    description=(
        "Backend API for the NoteMaster notes app.\n\n"
        "Designed to be called cleanly from a Next.js frontend: JSON request/response bodies, "
        "stable pagination fields, and consistent 4xx errors."
    ),
    version="0.1.0",
    openapi_tags=openapi_tags,
)

# Keep permissive CORS for template/dev environments.
# If you want to restrict this for production, set a specific allow_origins list.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/",
    tags=["Meta"],
    summary="Health check",
    operation_id="health_check",
)
def health_check():
    """
    PUBLIC_INTERFACE
    Simple health check endpoint.

    Returns:
        JSON object with a 'message' field.
    """
    return {"message": "Healthy"}


app.include_router(notes_router)
app.include_router(tags_router)
