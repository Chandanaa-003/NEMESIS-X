from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.analysis import Analysis
from app.models.live_session import LiveSession
from app.models.user import User
from app.services.report_service import generate_analysis_pdf_report, generate_live_session_pdf_report

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get(
    "/{analysis_id}/pdf",
    summary="Generate and download a PDF intelligence report for an owned analysis",
)
def download_analysis_pdf_report(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Build and stream a ReportLab PDF report from actual analysis database records."""
    analysis = (
        db.query(Analysis)
        .filter(Analysis.id == analysis_id, Analysis.user_id == current_user.id)
        .first()
    )
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis job not found.",
        )

    if analysis.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="PDF report generation requires a completed video analysis.",
        )

    pdf_path = generate_analysis_pdf_report(analysis=analysis, db=db)
    if not pdf_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate PDF report.",
        )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"nemesis-x-report-{analysis.id[:8]}.pdf",
    )


@router.get(
    "/live/{session_id}/pdf",
    summary="Generate and download a PDF intelligence report for a live monitoring session",
)
def download_live_session_pdf_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Build and stream a ReportLab PDF report for an owned live monitoring session."""
    live_session = (
        db.query(LiveSession)
        .filter(LiveSession.id == session_id, LiveSession.user_id == current_user.id)
        .first()
    )
    if live_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Live monitoring session not found.",
        )

    pdf_path = generate_live_session_pdf_report(live_session=live_session, db=db)
    if not pdf_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate live session PDF report.",
        )

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"nemesis-x-live-report-{live_session.id[:8]}.pdf",
    )
