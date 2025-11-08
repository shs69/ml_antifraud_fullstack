from app.models import Transaction, TransactionList, TransactionPublic, TransactionPublicList
from app.api.deps import CurrentUser, SessionDep
from app import crud
from fastapi import HTTPException, APIRouter, status


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
