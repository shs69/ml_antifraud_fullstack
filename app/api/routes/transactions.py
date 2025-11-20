from fastapi.responses import StreamingResponse
from app.models import Transaction, TransactionPublic, TransactionPublicList
from app.api.deps import CurrentUser, SessionDep
from app import crud
from fastapi import HTTPException, APIRouter, UploadFile, status
from app.utils import dict_to_transactions, csv_to_dict
from app.redis import sse_queue
import json

router = APIRouter(prefix="/transactions", tags=["transactions"])


async def event_generator():
    while True:
        await sse_queue.get()
        yield "data: updated\n\n"


@router.post("/")
async def create_transactions(session: SessionDep, current_user: CurrentUser, transaction_in: Transaction) -> TransactionPublic:
    transaction = crud.create_transaction(
        session=session, transaction_in=transaction_in, owner_id=current_user.id, home_coords=current_user.home_coord)
    if not crud.update_balance(session=session, transaction_in=transaction, current_user_email=current_user.email):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Authorized"
        )
    return TransactionPublic.model_validate(transaction)


@router.get("/")
def get_transactions(session: SessionDep, current_user: CurrentUser, start: int = 0, limit: int = 25) -> TransactionPublicList:
    data = crud.read_items(
        session=session, owner_id=current_user.id, skip=start, limit=limit)
    publicData = TransactionPublicList.model_validate(data)
    return publicData


@router.post("/file")
async def insert_transactions_from_file(session: SessionDep, current_user: CurrentUser, file: UploadFile):
    data = csv_to_dict(file)
    right_labels = ["shop_name", "shop_address", "is_refill",
                    "size", "used_chip", "used_pin_number", "online_order"]
    file_labels = list(data.keys())
    if set(file_labels) != set(right_labels):
        raise HTTPException(
            status_code=404, detail=f"Неверные колонки в файле: {file_labels}")

    transactions = dict_to_transactions(data)

    for transaction in transactions:
        crud.create_transaction(
            session=session, transaction_in=transaction, owner_id=current_user.id, home_coords=current_user.home_coord)

    return transactions


@router.get("/sse")
async def sse_transactions():
    return StreamingResponse(event_generator(), media_type="text/event-stream")
