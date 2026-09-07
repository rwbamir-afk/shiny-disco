from fastapi import APIRouter

from hokm.variants import supported_variants

router = APIRouter(prefix="/variants", tags=["variants"])


@router.get("")
async def list_variants() -> list[dict]:
    """Expose the product's variant catalog without implying unfinished modes are playable."""
    return supported_variants()
