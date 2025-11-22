"""PDF report exporter for paper summaries."""
import os
from typing import Any
from datetime import datetime
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from src.config.logging import get_logger

logger = get_logger(__name__)


class PDFExporter:
    """PDF exporter implementing TDS §4.4 contract."""

    def __init__(self, output_dir: str = "data/reports"):
        """Initialize PDF exporter.

        Args:
            output_dir: Directory for PDF output
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Register Chinese font if available (fallback to default if not)
        self._setup_fonts()

    def _setup_fonts(self) -> None:
        """Setup fonts for Chinese characters."""
        # Try to register a Chinese font
        # In production, you'd need to include a Chinese font file
        # For now, we'll use the default which has some Unicode support
        try:
            # Example: Register a Chinese font if available
            # pdfmetrics.registerFont(TTFont('SimHei', 'SimHei.ttf'))
            self.chinese_font = None  # Will use default
            logger.info("pdf_fonts_setup", chinese_font="default")
        except Exception as e:
            logger.warning("pdf_font_registration_failed", error=str(e))
            self.chinese_font = None

    def export(
        self,
        paper_metadata: dict[str, Any],
        summary: dict[str, Any],
        options: dict[str, Any] = None
    ) -> dict[str, Any]:
        """Export summary to PDF.

        Args:
            paper_metadata: Paper metadata from arXiv
            summary: Summary from LLM pipeline
            options: Export options (template, branding, etc.)

        Returns:
            Dict with pdf_path, size_bytes
        """
        options = options or {}
        arxiv_id = paper_metadata["arxiv_id"].split('v')[0]

        # Generate filename
        filename = f"{arxiv_id}_report.pdf"
        pdf_path = self.output_dir / filename

        logger.info("pdf_export_start", arxiv_id=arxiv_id, path=str(pdf_path))

        try:
            # Create PDF
            doc = SimpleDocTemplate(
                str(pdf_path),
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18,
            )

            # Build content
            story = []
            styles = self._create_styles()

            # Header
            story.append(Paragraph("arXiv 論文摘要報告", styles["CustomTitle"]))
            story.append(Spacer(1, 0.2 * inch))

            # Metadata
            story.append(Paragraph(f"<b>標題：</b>{paper_metadata['title']}", styles["CustomNormal"]))
            story.append(Spacer(1, 0.1 * inch))

            authors = ", ".join(paper_metadata['authors'][:5])  # Limit authors
            if len(paper_metadata['authors']) > 5:
                authors += " et al."
            story.append(Paragraph(f"<b>作者：</b>{authors}", styles["CustomNormal"]))
            story.append(Spacer(1, 0.1 * inch))

            story.append(Paragraph(
                f"<b>arXiv ID：</b>{paper_metadata['arxiv_id']}", styles["CustomNormal"]
            ))
            story.append(Spacer(1, 0.1 * inch))

            story.append(Paragraph(
                f"<b>類別：</b>{paper_metadata['primary_category']}", styles["CustomNormal"]
            ))
            story.append(Spacer(1, 0.1 * inch))

            story.append(Paragraph(
                f"<b>發表日期：</b>{paper_metadata.get('published', 'N/A')[:10]}", styles["CustomNormal"]
            ))
            story.append(Spacer(1, 0.3 * inch))

            # Summary sections
            sections = [
                ("intro", "簡介"),
                ("background", "背景"),
                ("method", "方法"),
                ("conclusion", "結論"),
            ]

            for key, title in sections:
                if key in summary:
                    story.append(Paragraph(title, styles["CustomHeading2"]))
                    story.append(Spacer(1, 0.1 * inch))
                    story.append(Paragraph(summary[key], styles["CustomNormal"]))
                    story.append(Spacer(1, 0.2 * inch))

            # Bullet points
            if "bullet_points" in summary:
                story.append(Paragraph("重點摘要", styles["CustomHeading2"]))
                story.append(Spacer(1, 0.1 * inch))
                for point in summary["bullet_points"]:
                    story.append(Paragraph(f"• {point}", styles["CustomNormal"]))
                    story.append(Spacer(1, 0.05 * inch))
                story.append(Spacer(1, 0.2 * inch))

            # Limitations
            if "limitations" in summary:
                story.append(Paragraph("限制", styles["CustomHeading2"]))
                story.append(Spacer(1, 0.1 * inch))
                story.append(Paragraph(summary["limitations"], styles["CustomNormal"]))
                story.append(Spacer(1, 0.3 * inch))

            # Footer
            footer_text = options.get("footer_note", "Generated by Discord Research Assistant")
            story.append(Spacer(1, 0.5 * inch))
            story.append(Paragraph(
                f"<i>{footer_text}</i><br/><i>生成時間：{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>",
                styles["CustomFooter"]
            ))

            # Build PDF
            doc.build(story)

            # Get file size
            size_bytes = os.path.getsize(pdf_path)

            logger.info("pdf_export_complete", arxiv_id=arxiv_id, size_bytes=size_bytes)

            return {
                "pdf_path": str(pdf_path),
                "size_bytes": size_bytes,
            }

        except Exception as e:
            logger.error("pdf_export_error", arxiv_id=arxiv_id, error=str(e))
            raise

    def _create_styles(self) -> dict:
        """Create PDF styles.

        Returns:
            Dict of styles
        """
        styles = getSampleStyleSheet()

        # Custom title style (unique name to avoid conflicts)
        styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f77b4'),
            spaceAfter=12,
            alignment=TA_CENTER,
        ))

        # Custom heading2 style
        styles.add(ParagraphStyle(
            name='CustomHeading2',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2c3e50'),
            spaceBefore=6,
            spaceAfter=6,
        ))

        # Custom normal text style
        styles.add(ParagraphStyle(
            name='CustomNormal',
            parent=styles['BodyText'],
            fontSize=11,
            leading=14,
            alignment=TA_LEFT,
        ))

        # Custom footer style
        styles.add(ParagraphStyle(
            name='CustomFooter',
            parent=styles['BodyText'],
            fontSize=9,
            textColor=colors.grey,
            alignment=TA_CENTER,
        ))

        return styles
