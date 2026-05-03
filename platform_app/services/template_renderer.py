import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import qrcode
from reportlab.lib.pagesizes import A5, A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


PAGE_SIZES = {
    "A5": A5,
    "A4": A4,
}


@dataclass
class RenderResult:
    pdf_path: str
    qr_path: str
    invite_url: str


class TemplateRenderer:
    def __init__(self, storage_dir: str):
        self.storage_dir = os.path.abspath(storage_dir)

    def render_invitation(
        self,
        *,
        template_id: str,
        variables: Dict[str, Any],
        invitation_code: str,
        base_public_url: str,
        pdf_path: str,
        qr_path: str,
    ) -> RenderResult:
        template = self._load_template(template_id)
        template_dir = template["_template_dir"]

        invite_url = self._build_invite_url(base_public_url, invitation_code)

        final_variables = {
            **variables,
            "invite_url": invite_url,
        }

        self._ensure_dir(os.path.dirname(qr_path))
        self._ensure_dir(os.path.dirname(pdf_path))

        self._make_qr_png(qr_path, invite_url)

        page_size_name = str(template.get("page_size", "A5")).upper()
        page_w, page_h = PAGE_SIZES.get(page_size_name, A5)

        pdf = canvas.Canvas(pdf_path, pagesize=(page_w, page_h))

        pages = template.get("pages") or []
        if not pages:
            raise ValueError(f"Template {template_id} invalide: aucune page définie.")

        for page in pages:
            self._draw_page(
                pdf=pdf,
                page=page,
                template_dir=template_dir,
                variables=final_variables,
                qr_path=qr_path,
                page_w=page_w,
                page_h=page_h,
            )
            pdf.showPage()

        pdf.save()

        return RenderResult(
            pdf_path=pdf_path,
            qr_path=qr_path,
            invite_url=invite_url,
        )

    def _load_template(self, template_id: str) -> Dict[str, Any]:
        template_dir = os.path.join(self.storage_dir, "templates", template_id)
        template_json_path = os.path.join(template_dir, "template.json")

        if not os.path.exists(template_json_path):
            raise FileNotFoundError(f"Template JSON introuvable: {template_json_path}")

        with open(template_json_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        data["_template_dir"] = template_dir
        return data

    def _draw_page(
        self,
        *,
        pdf: canvas.Canvas,
        page: Dict[str, Any],
        template_dir: str,
        variables: Dict[str, Any],
        qr_path: str,
        page_w: float,
        page_h: float,
    ) -> None:
        background = page.get("background")

        if background:
            background_path = os.path.join(template_dir, background)

            if not os.path.exists(background_path):
                raise FileNotFoundError(f"Image de fond introuvable: {background_path}")

            pdf.drawImage(
                ImageReader(background_path),
                0,
                0,
                width=page_w,
                height=page_h,
                preserveAspectRatio=False,
                mask="auto",
            )

        for element in page.get("elements", []):
            element_type = str(element.get("type", "")).lower()

            if element_type == "text":
                self._draw_text_element(
                    pdf=pdf,
                    element=element,
                    variables=variables,
                )

            elif element_type == "qr":
                self._draw_qr_element(
                    pdf=pdf,
                    element=element,
                    qr_path=qr_path,
                )

            elif element_type == "rsvp_link":
                self._draw_rsvp_link_element(
                    pdf=pdf,
                    element=element,
                    variables=variables,
                )

    def _draw_text_element(
        self,
        *,
        pdf: canvas.Canvas,
        element: Dict[str, Any],
        variables: Dict[str, Any],
    ) -> None:
        key = element.get("key")
        text = self._safe_text(variables.get(key))

        if not text:
            return

        x = float(element.get("x_mm", 0)) * mm
        y = float(element.get("y_mm", 0)) * mm

        font_name = element.get("font", "Helvetica")
        font_size = int(element.get("size", element.get("font_size", 12)))
        align = str(element.get("align", "left")).lower()
        max_width_mm = element.get("max_width_mm")

        pdf.setFont(font_name, font_size)

        if max_width_mm:
            lines = self._wrap_text(
                text=text,
                font_name=font_name,
                font_size=font_size,
                max_width=float(max_width_mm) * mm,
            )
        else:
            lines = [text]

        line_height = float(element.get("line_height", font_size * 1.25))

        for index, line in enumerate(lines):
            current_y = y - (index * line_height)

            if align == "center":
                pdf.drawCentredString(x, current_y, line)
            elif align == "right":
                pdf.drawRightString(x, current_y, line)
            else:
                pdf.drawString(x, current_y, line)

    def _draw_qr_element(
        self,
        *,
        pdf: canvas.Canvas,
        element: Dict[str, Any],
        qr_path: str,
    ) -> None:
        if not os.path.exists(qr_path):
            return

        x = float(element.get("x_mm", 0)) * mm
        y = float(element.get("y_mm", 0)) * mm
        w = float(element.get("w_mm", 25)) * mm
        h = float(element.get("h_mm", 25)) * mm

        pdf.drawImage(
            ImageReader(qr_path),
            x,
            y,
            width=w,
            height=h,
            mask="auto",
        )

    def _draw_rsvp_link_element(
        self,
        *,
        pdf: canvas.Canvas,
        element: Dict[str, Any],
        variables: Dict[str, Any],
    ) -> None:
        invite_url = self._safe_text(variables.get("invite_url"))

        if not invite_url:
            return

        action = self._safe_text(element.get("action")).lower()

        if action not in ("yes", "no", "later"):
            return

        url = f"{invite_url}/rsvp?status={action}"

        x = float(element.get("x_mm", 0)) * mm
        y = float(element.get("y_mm", 0)) * mm
        w = float(element.get("w_mm", 80)) * mm
        h = float(element.get("h_mm", 10)) * mm

        pdf.linkURL(
            url,
            (x, y, x + w, y + h),
            relative=0,
            thickness=0,
        )

    def _make_qr_png(self, save_path: str, data: str) -> None:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )

        qr.add_data(data)
        qr.make(fit=True)

        image = qr.make_image(fill_color="black", back_color="white")
        image.save(save_path)

    def _build_invite_url(self, base_public_url: str, invitation_code: str) -> str:
        base = (base_public_url or "").rstrip("/")
        return f"{base}/i/{invitation_code}" if base else f"/i/{invitation_code}"

    def _wrap_text(
        self,
        *,
        text: str,
        font_name: str,
        font_size: int,
        max_width: float,
    ) -> list[str]:
        words = text.split()
        lines = []
        current = ""

        for word in words:
            candidate = f"{current} {word}".strip()

            if stringWidth(candidate, font_name, font_size) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word

        if current:
            lines.append(current)

        return lines

    def _safe_text(self, value: Optional[Any]) -> str:
        if value is None:
            return ""

        return " ".join(str(value).split()).strip()

    def _ensure_dir(self, path: str) -> None:
        os.makedirs(path, exist_ok=True)