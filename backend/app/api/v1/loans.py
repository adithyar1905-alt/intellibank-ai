from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
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
from app.models.audit import AuditLog
from app.schemas.loan import (
    LoanApplicationCreate,
    LoanApplicationResponse,
    LoanDetailResponse,
    LoanDocumentResponse,
    LoanEligibilityResponse,
    LoanRepaymentResponse,
    LoanRejectionRequest,
    LoanReviewResponse,
)
from app.services.customer.document_storage import (
    detect_document_type,
    document_extension,
    document_media_type,
    load_document,
)
from app.services.loan_service import (
    LOAN_OFFICER_ROLES,
    _application_access,
    _get_application,
    approve_application,
    calculate_emi,
    check_eligibility,
    get_application,
    get_loan_document,
    loan_details,
    list_applications,
    pay_repayment,
    reject_application,
    review_application,
    submit_application,
    upload_loan_document,
    withdraw_application,
)


router = APIRouter(prefix="/loans", tags=["loans"])
DatabaseSession = Annotated[Session, Depends(get_db)]
MAX_LOAN_DOCUMENT_BYTES = 10 * 1024 * 1024
APPLICATION_STATUS = (
    "^(submitted|under_review|approved|rejected|withdrawn|disbursed)$"
)


def _source_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


@router.post(
    "/eligibility",
    response_model=LoanEligibilityResponse,
)
def loan_eligibility(
    payload: LoanApplicationCreate,
    session: DatabaseSession,
    actor: CurrentUser,
) -> LoanEligibilityResponse:
    return check_eligibility(session, payload, actor)


@router.post(
    "/applications",
    response_model=LoanApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def apply_for_loan(
    payload: LoanApplicationCreate,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> LoanApplicationResponse:
    application = submit_application(
        session, payload, actor, _source_ip(request)
    )
    return LoanApplicationResponse.model_validate(application)


@router.get(
    "/applications",
    response_model=list[LoanApplicationResponse],
)
def search_applications(
    session: DatabaseSession,
    actor: CurrentUser,
    application_status: Annotated[
        str | None, Query(alias="status", pattern=APPLICATION_STATUS)
    ] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> list[LoanApplicationResponse]:
    applications = list_applications(
        session,
        actor,
        status_filter=application_status,
        offset=offset,
        limit=limit,
    )
    return [LoanApplicationResponse.model_validate(item) for item in applications]


@router.get(
    "/applications/{application_id}",
    response_model=LoanApplicationResponse,
)
def get_application_profile(
    application_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
) -> LoanApplicationResponse:
    application = get_application(session, application_id, actor)
    return LoanApplicationResponse.model_validate(application)


@router.post(
    "/applications/{application_id}/documents",
    response_model=LoanDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    application_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
    document_type: Annotated[
        str, Form(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9 _-]+$")
    ],
    file: Annotated[UploadFile, File()],
) -> LoanDocumentResponse:
    application = _get_application(session, application_id)
    _application_access(application, actor)
    content = await file.read(MAX_LOAN_DOCUMENT_BYTES + 1)
    await file.close()
    if not content:
        raise HTTPException(status_code=422, detail="The uploaded document is empty.")
    if len(content) > MAX_LOAN_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=413, detail="Loan documents must not exceed 10 MiB."
        )
    extension, inferred_media_type = detect_document_type(content)
    if file.content_type not in {None, "application/octet-stream", inferred_media_type}:
        raise HTTPException(
            status_code=415,
            detail="The uploaded file content does not match its media type.",
        )
    submitted_extension = Path(file.filename or "").suffix.lower()
    allowed_extensions = {extension, ".jpeg"} if extension == ".jpg" else {extension}
    if submitted_extension and submitted_extension not in allowed_extensions:
        raise HTTPException(
            status_code=415,
            detail="The uploaded file extension does not match its content.",
        )
    normalized_type = document_type.strip()
    if not normalized_type:
        raise HTTPException(status_code=422, detail="Document type cannot be blank.")
    document = upload_loan_document(
        session,
        application_id,
        actor,
        document_type=normalized_type,
        content=content,
        extension=extension,
        source_ip=_source_ip(request),
    )
    return LoanDocumentResponse.model_validate(document)


@router.get(
    "/applications/{application_id}/documents/{document_id}/download",
)
def download_document(
    application_id: UUID,
    document_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> Response:
    document = get_loan_document(session, application_id, document_id, actor)
    extension = document_extension(document.document_reference)
    content = load_document(document.document_reference)
    session.add(
        AuditLog(
            actor_id=actor.id,
            action="loan.document_download",
            resource_type="loan_application",
            resource_id=application_id,
            source_ip=_source_ip(request),
            details={"document_id": str(document_id)},
        )
    )
    session.commit()
    return Response(
        content=content,
        media_type=document_media_type(extension),
        headers={
            "Content-Disposition": f'attachment; filename="loan-document-{document.id}{extension}"',
            "Cache-Control": "no-store",
        },
    )


@router.post(
    "/applications/{application_id}/review",
    response_model=LoanApplicationResponse,
    dependencies=[Depends(require_roles(*LOAN_OFFICER_ROLES))],
)
def review(
    application_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> LoanApplicationResponse:
    application = review_application(
        session, application_id, actor, _source_ip(request)
    )
    return LoanApplicationResponse.model_validate(application)


@router.post(
    "/applications/{application_id}/approve",
    response_model=LoanReviewResponse,
    dependencies=[Depends(require_roles(*LOAN_OFFICER_ROLES))],
)
def approve(
    application_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> LoanReviewResponse:
    loan = approve_application(session, application_id, actor, _source_ip(request))
    return LoanReviewResponse(
        id=loan.id,
        customer_id=loan.customer_id,
        loan_type=loan.loan_type,
        principal=loan.principal,
        interest_rate=loan.interest_rate,
        term_months=loan.term_months,
        currency=loan.currency,
        status=loan.status,
        outstanding_balance=loan.outstanding_balance,
        emi_amount=calculate_emi(loan.principal, loan.interest_rate, loan.term_months),
        created_at=loan.created_at,
    )


@router.post(
    "/applications/{application_id}/reject",
    response_model=LoanApplicationResponse,
    dependencies=[Depends(require_roles(*LOAN_OFFICER_ROLES))],
)
def reject(
    application_id: UUID,
    payload: LoanRejectionRequest,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> LoanApplicationResponse:
    application = reject_application(
        session, application_id, payload.reason, actor, _source_ip(request)
    )
    return LoanApplicationResponse.model_validate(application)


@router.delete(
    "/applications/{application_id}",
    response_model=LoanApplicationResponse,
)
def withdraw(
    application_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
) -> LoanApplicationResponse:
    application = withdraw_application(
        session, application_id, actor, _source_ip(request)
    )
    return LoanApplicationResponse.model_validate(application)


@router.get("/{loan_id}", response_model=LoanDetailResponse)
def get_loan(
    loan_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
) -> LoanDetailResponse:
    loan = loan_details(session, loan_id, actor)
    return LoanDetailResponse(
        id=loan.id,
        customer_id=loan.customer_id,
        loan_type=loan.loan_type,
        principal=loan.principal,
        interest_rate=loan.interest_rate,
        term_months=loan.term_months,
        currency=loan.currency,
        status=loan.status,
        outstanding_balance=loan.outstanding_balance,
        emi_amount=calculate_emi(loan.principal, loan.interest_rate, loan.term_months),
        created_at=loan.created_at,
        repayments=[
            LoanRepaymentResponse.model_validate(item)
            for item in sorted(loan.repayments, key=lambda row: row.due_at)
        ],
    )


@router.post(
    "/{loan_id}/repayments/{repayment_id}/pay",
    response_model=LoanRepaymentResponse,
)
def pay(
    loan_id: UUID,
    repayment_id: UUID,
    account_id: UUID,
    session: DatabaseSession,
    actor: CurrentUser,
    request: Request,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=8, max_length=120)
    ],
) -> LoanRepaymentResponse:
    repayment = pay_repayment(
        session,
        loan_id,
        repayment_id,
        account_id,
        actor,
        idempotency_key,
        _source_ip(request),
    )
    return LoanRepaymentResponse.model_validate(repayment)