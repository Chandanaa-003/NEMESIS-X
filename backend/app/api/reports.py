from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.analysis import Analysis
from app.models.user import User
from app.services.report_service import generate_analysis_pdf_report

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
