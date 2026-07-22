from fastapi import APIRouter, Response

router = APIRouter()


@router.post("/webhooks/github")
async def receive_github_webhook() -> Response:
    return Response(status_code=501)
