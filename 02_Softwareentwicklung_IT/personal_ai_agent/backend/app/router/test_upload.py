from fastapi import APIRouter
router = APIRouter(prefix="/api", tags=["test"])
@router.get("/test-version")
async def test_version():
    return {"version": "upload-implemented"}
