from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/queue")


@router.get("")
def status(request: Request) -> dict:
    return request.app.state.queue.status()


@router.post("/resume")
def resume(request: Request) -> dict:
    request.app.state.queue.resume()
    return request.app.state.queue.status()
