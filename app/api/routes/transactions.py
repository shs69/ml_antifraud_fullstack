from app.models import Transaction, TransactionPublic, TransactionPublicList
from app.api.deps import CurrentUser, SessionDep
from app import crud
from fastapi import HTTPException, APIRouter, UploadFile, status
from app.utils import dict_to_transactions, csv_to_dict
import asyncio

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/")
async def create_transactions(session: SessionDep, current_user: CurrentUser, transaction_in: Transaction) -> TransactionPublic:
    transaction = await crud.create_transaction(
        session=session, transaction_in=transaction_in, owner_id=current_user.id, home_coords=current_user.home_coord)
    if not crud.update_balance(session=session, transaction_in=transaction, current_user_email=current_user.email):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Authorized"
        )
    return TransactionPublic.model_validate(transaction)


@router.get("/")
def get_transactions(session: SessionDep, current_user: CurrentUser) -> TransactionPublicList:
    data = crud.read_items(session=session, owner_id=current_user.id)
    publicData = TransactionPublicList.model_validate(data)
    return publicData


# @router.post("/update_transaction/")
# def update_transaction(session: SessionDep, current_user: CurrentUser, model_update: TransactionUpdateFraud):
#     correct_values = ["0", "1", 1, 0]
#     if model_update.fraud not in correct_values:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Incorrect value of fraud")
#     fraud = crud.update_transaction(
#         session=session, transaction_id=model_update.id, fraud_value=model_update.fraud)
#     return fraud

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

    # tasks = [
    #     crud.create_transaction(
    #         session=session,
    #         transaction_in=transaction,
    #         home_coords=current_user.home_coord,
    #         owner_id=current_user.id
    #     )
    #     for transaction in transactions
    # ]
    # await asyncio.gather(*tasks)

    for transaction in transactions:
        await crud.create_transaction(session=session, transaction_in=transaction, home_coords=current_user.home_coord, owner_id=current_user.id)

    return transactions
