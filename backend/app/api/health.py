from fastapi import APIRouter, Response, status

router = APIRouter()

_ready = {"value": False}


def mark_ready() -> None:
    _ready["value"] = True


def is_ready() -> bool:
    return _ready["value"]


@router.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


@router.get("/readyz")
async def readyz(response: Response) -> dict:
    if not _ready["value"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"ok": False, "reason": "model_not_loaded"}
    return {"ok": True}
