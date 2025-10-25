from app.models import Transaction, TransactionList
from app.api.deps import CurrentUser, SessionDep
from app import crud
from fastapi import HTTPException, APIRouter, status


router = APIRouter(prefix="/transactions", tags=["transactions"])

@router.post("/", response_model=Transaction)
def create_transactions(session: SessionDep, current_user: CurrentUser, transaction_in: Transaction):
    transaction = crud.create_transaction(session=session, transaction_in=transaction_in, owner_id=current_user.id)
    if not crud.update_balance(session=session, transaction_in=transaction, current_user_email=current_user.email):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Authorized"
        )
    return transaction_in

@router.get("/")
def get_transactions(session: SessionDep, current_user: CurrentUser) -> TransactionList:
    data = crud.read_items(session=session, owner_id=current_user.id)
    return data