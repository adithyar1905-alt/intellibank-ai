from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.authentication import CurrentUser
from app.core.authorization import require_roles
from app.database import get_db
from app.models.customer import Customer
from app.models.user import User
from app.repositories.customer_repository import get_customer
from app.schemas.customer import (
    AccountHistoryItem,
    CustomerCreate,
    CustomerProfileResponse,
    CustomerRiskProfile,
    CustomerStatusUpdate,
    CustomerUpdate,
    KYCDocumentResponse,
    KYCUploadResponse,
    KYCVerificationUpdate,
)
from app.services.customer.document_storage import (
    detect_document_type,
    document_extension,
    document_media_type,
    load_document,
)
from app.services.customer.service import (
    account_history,
    audit_document_download,
    create_customer,
    customer_profile,
    customer_risk_profile,
    decimal_amount,
    deactivate_customer,
    find_customers,
    get_customer_document,
    update_customer,
    update_customer_status,
    upload_kyc_document,
    verify_kyc_document,
)


router = APIRouter(prefix="/customers", tags=["customers"])
DatabaseSession = Annotated[Session, Depends(get_db)]

STAFF_ROLES = ("Super Admin", "Bank Admin", "Branch Manager", "Bank Employee")
RISK_ROLES = (*STAFF_ROLES, "Risk Analyst")
MAX_KYC_DOCUMENT_BYTES = 10 * 1024 * 1024


def _source_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


def _has_staff_role(user: User, roles: tuple[str, ...] = STAFF_ROLES) -> bool:
    names = {role.name for role in user.roles}
    return "Super Admin" in names or bool(names.intersection(roles))


def _assert_customer_access(customer: Customer, user: User) -> None:
    if _has_staff_role(user) or (
        "Customer" in {role.name for role in user.roles}
        and customer.user_id == user.id
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You are not allowed to access this customer.",
    )


def _require_customer(session: Session, customer_id: UUID) -> Customer:
    customer = get_customer(session, customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found."
        )
    return customer


@router.post(
    "",
    response_model=CustomerProfileResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*STAFF_ROLES))],
)
def create(
    payload: CustomerCreate,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> CustomerProfileResponse:
    customer = create_customer(session, payload, actor, _source_ip(request))
    return customer_profile(customer)


@router.get(
    "",
    response_model=list[CustomerProfileResponse],
    dependencies=[Depends(require_roles(*STAFF_ROLES))],
)
def search(
    session: DatabaseSession,
    query: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    customer_status: Annotated[
        str | None, Query(alias="status", pattern="^(active|inactive|blocked)$")
    ] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> list[CustomerProfileResponse]:
    customers = find_customers(
        session,
        query=query,
        status_filter=customer_status,
        offset=offset,
        limit=limit,
    )
    return [customer_profile(customer) for customer in customers]


@router.get("/{customer_id}", response_model=CustomerProfileResponse)
def get_profile(
    customer_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
) -> CustomerProfileResponse:
    customer = _require_customer(session, customer_id)
    _assert_customer_access(customer, actor)
    return customer_profile(customer)


@router.patch(
    "/{customer_id}",
    response_model=CustomerProfileResponse,
    dependencies=[Depends(require_roles(*STAFF_ROLES))],
)
def update(
    customer_id: UUID,
    payload: CustomerUpdate,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> CustomerProfileResponse:
    customer = update_customer(
        session, customer_id, payload, actor, _source_ip(request)
    )
    return customer_profile(customer)


@router.patch(
    "/{customer_id}/status",
    response_model=CustomerProfileResponse,
    dependencies=[Depends(require_roles(*STAFF_ROLES))],
)
def set_status(
    customer_id: UUID,
    payload: CustomerStatusUpdate,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> CustomerProfileResponse:
    customer = update_customer_status(
        session, customer_id, payload.status, actor, _source_ip(request)
    )
    return customer_profile(customer)


@router.delete(
    "/{customer_id}",
    response_model=CustomerProfileResponse,
    dependencies=[Depends(require_roles(*STAFF_ROLES))],
)
def deactivate(
    customer_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> CustomerProfileResponse:
    customer = deactivate_customer(session, customer_id, actor, _source_ip(request))
    return customer_profile(customer)


@router.post(
    "/{customer_id}/kyc-documents",
    response_model=KYCUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_kyc(
    customer_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
    document_type: Annotated[
        str, Form(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9 _-]+$")
    ],
    file: Annotated[UploadFile, File()],
    document_number: Annotated[
        str | None, Form(min_length=4, max_length=64, pattern=r"^[A-Za-z0-9-]+$")
    ] = None,
    expires_at: Annotated[datetime | None, Form()] = None,
) -> KYCUploadResponse:
    customer = _require_customer(session, customer_id)
    _assert_customer_access(customer, actor)
    content = await file.read(MAX_KYC_DOCUMENT_BYTES + 1)
    await file.close()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The uploaded document is empty.",
        )
    if len(content) > MAX_KYC_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="KYC documents must not exceed 10 MiB.",
        )
    extension, inferred_media_type = detect_document_type(content)
    if file.content_type not in {None, "application/octet-stream", inferred_media_type}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The uploaded file content does not match its media type.",
        )
    submitted_extension = Path(file.filename or "").suffix.lower()
    allowed_extensions = {extension, ".jpeg"} if extension == ".jpg" else {extension}
    if submitted_extension and submitted_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The uploaded file extension does not match its content.",
        )
    doc_type = document_type.strip()
    if not doc_type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document type cannot be blank.",
        )
    document = upload_kyc_document(
        session,
        customer,
        actor,
        document_type=doc_type,
        content=content,
        extension=extension,
        document_number_last4=document_number[-4:] if document_number else None,
        expires_at=expires_at,
        source_ip=_source_ip(request),
    )
    return KYCUploadResponse.model_validate(document)


@router.patch(
    "/{customer_id}/kyc-documents/{document_id}",
    response_model=KYCDocumentResponse,
    dependencies=[Depends(require_roles(*STAFF_ROLES))],
)
def review_kyc(
    customer_id: UUID,
    document_id: UUID,
    payload: KYCVerificationUpdate,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> KYCDocumentResponse:
    document = verify_kyc_document(
        session,
        customer_id,
        document_id,
        payload,
        actor,
        _source_ip(request),
    )
    return KYCDocumentResponse.model_validate(document)


@router.get("/{customer_id}/kyc-documents/{document_id}/download")
def download_kyc(
    customer_id: UUID,
    document_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> Response:
    customer = _require_customer(session, customer_id)
    _assert_customer_access(customer, actor)
    document = get_customer_document(session, customer_id, document_id)
    extension = document_extension(document.document_reference)
    content = load_document(document.document_reference)
    audit_document_download(
        session, customer_id, document_id, actor, _source_ip(request)
    )
    return Response(
        content=content,
        media_type=document_media_type(extension),
        headers={
            "Content-Disposition": (
                f'attachment; filename="kyc-document-{document.id}{extension}"'
            ),
            "Cache-Control": "no-store",
        },
    )


@router.get(
    "/{customer_id}/account-history",
    response_model=list[AccountHistoryItem],
)
def get_account_history(
    customer_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> list[AccountHistoryItem]:
    customer = _require_customer(session, customer_id)
    _assert_customer_access(customer, actor)
    entries = account_history(session, customer_id, offset=offset, limit=limit)
    return [
        AccountHistoryItem(
            transaction_id=transaction.id,
            account_id=account.id,
            account_number_last4=account.account_number[-4:],
            reference=transaction.reference,
            transaction_type=transaction.transaction_type,
            amount=decimal_amount(transaction.amount),
            currency=transaction.currency,
            status=transaction.status,
            description=transaction.description,
            created_at=transaction.created_at,
        )
        for transaction, account in entries
    ]


@router.get(
    "/{customer_id}/risk-profile",
    response_model=CustomerRiskProfile,
    dependencies=[Depends(require_roles(*RISK_ROLES))],
)
def get_risk_profile(
    customer_id: UUID, session: DatabaseSession
) -> CustomerRiskProfile:
    return customer_risk_profile(session, customer_id)