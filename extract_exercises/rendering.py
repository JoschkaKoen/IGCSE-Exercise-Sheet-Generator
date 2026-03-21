# -*- coding: utf-8 -*-
"""Rasterize PDF regions to strips and assemble output PDFs."""

import io

import fitz
from PIL import Image, ImageDraw

from .config import (
    A4_HEIGHT_PT,
    A4_WIDTH_PT,
    DPI,
    HEADER_ZONE_MAX_Y_PT,
    MS_LANDSCAPE_H_THRESHOLD_PT,
    MS_LANDSCAPE_MARGIN_PT,
    MS_MARKS_START_PT,
    MS_TABLE_LEFT_PT,
    QR_MARGIN_ZONE_PT,
    QR_MAX_SIZE_PT,
    STRIP_CROP_LEFT_PT,
    STRIP_CROP_RIGHT_PT,
    STRIP_CROP_TOP_PT,
)
from .fonts import (
    draw_exam_label_pil,
    draw_page_header_pil,
    header_band_px,
    pil_font,
    pil_font_bold,
)


def scale_and_page_dims():
    scale = DPI / 72.0
    page_width_px = int(A4_WIDTH_PT * scale)
    page_height_px = int(A4_HEIGHT_PT * scale)
    return scale, page_width_px, page_height_px


def insets_for_strip(y_start_pt: float, page_height_pt: float, scale: float) -> tuple[int, int, int]:
    """
    Pixels to crop from the left, right, and top of this strip's raster.

    Side crops are always applied (removes vertical gray margin bands that span
    the full page height). Top crop is only applied for strips starting in the
    upper header zone (removes QR codes / exam boilerplate at the top of pages).
    """
    _ = page_height_pt
    in_header = y_start_pt <= HEADER_ZONE_MAX_Y_PT
    l = int(STRIP_CROP_LEFT_PT * scale)
    r = int(STRIP_CROP_RIGHT_PT * scale)
    t = int(STRIP_CROP_TOP_PT * scale) if in_header else 0
    return l, r, t


def h_center_x(strip_w: int, page_w: int) -> int:
    return max(0, (page_w - strip_w) // 2)


def blank_qr_codes_on_page(img: Image.Image, page: fitz.Page, scale: float) -> None:
    """Detect and white-out QR codes in the rasterized page image."""
    pw, ph = page.rect.width, page.rect.height
    draw = ImageDraw.Draw(img)

    try:
        for img_item in page.get_images():
            xref = img_item[0]
            try:
                rects = page.get_image_rects(xref)
            except Exception:
                continue
            for rect in rects:
                iw, ih = rect.width, rect.height
                if iw < 5 or ih < 5:
                    continue
                if iw > QR_MAX_SIZE_PT or ih > QR_MAX_SIZE_PT:
                    continue
                if max(iw, ih) / min(iw, ih) > 2.0:
                    continue
                in_margin = (
                    rect.x0 < QR_MARGIN_ZONE_PT
                    or rect.x1 > pw - QR_MARGIN_ZONE_PT
                    or rect.y0 < QR_MARGIN_ZONE_PT
                    or rect.y1 > ph - QR_MARGIN_ZONE_PT
                )
                if in_margin:
                    px0 = max(0, int(rect.x0 * scale))
                    py0 = max(0, int(rect.y0 * scale))
                    px1 = min(img.width, int(rect.x1 * scale))
                    py1 = min(img.height, int(rect.y1 * scale))
                    draw.rectangle([px0, py0, px1, py1], fill=(255, 255, 255))
    except Exception:
        pass

    corner_pt = min(QR_MAX_SIZE_PT + 10, QR_MARGIN_ZONE_PT)
    cs = int(corner_pt * scale)
    w_px, h_px = img.size
    corners = [
        (0, 0, cs, cs),
        (w_px - cs, 0, w_px, cs),
        (0, h_px - cs, cs, h_px),
        (w_px - cs, h_px - cs, w_px, h_px),
    ]
    gray = img.convert("L")
    for bx0, by0, bx1, by1 in corners:
        bx0, by0 = max(0, bx0), max(0, by0)
        bx1, by1 = min(w_px, bx1), min(h_px, by1)
        if bx1 <= bx0 or by1 <= by0:
            continue
        region = gray.crop((bx0, by0, bx1, by1))
        rw, rh = region.size
        if rw < 10 or rh < 10:
            continue

        pixels = list(region.getdata())
        dark = sum(1 for p in pixels if p < 100)
        ratio = dark / len(pixels)
        if not (0.20 <= ratio <= 0.65):
            continue

        mid_y = rh // 2
        row = [region.getpixel((x, mid_y)) for x in range(rw)]
        transitions = sum(1 for i in range(1, len(row)) if (row[i] < 100) != (row[i - 1] < 100))
        if transitions >= rw // 5:
            draw.rectangle([bx0, by0, bx1, by1], fill=(255, 255, 255))


def collect_strips_from_regions(doc, regions):
    """Rasterize regions to image strips (one continuous list for layout)."""
    scale, page_width_px, _ = scale_and_page_dims()
    separator_height = int(8 * scale)

    rendered_pages = {}
    needed_pages = set(r[1] for r in regions)
    print(f"  Rendering {len(needed_pages)} source page(s) at {DPI} DPI...")
    for pi in needed_pages:
        mat = fitz.Matrix(scale, scale)
        pix = doc[pi].get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        blank_qr_codes_on_page(img, doc[pi], scale)
        rendered_pages[pi] = img

    strips = []
    current_qnum = None

    for qnum, page_idx, y_start, y_end in regions:
        img = rendered_pages[page_idx]
        page_h_pt = doc[page_idx].rect.height
        py_start = int(y_start * scale)
        py_end = int(y_end * scale)
        py_start = max(0, min(py_start, img.height - 1))
        py_end = max(py_start + 1, min(py_end, img.height))

        if page_h_pt < MS_LANDSCAPE_H_THRESHOLD_PT:
            x0_px = max(0, int(MS_TABLE_LEFT_PT * scale))
            x1_px = min(img.width, int(MS_MARKS_START_PT * scale))
            strip_raw = img.crop((x0_px, py_start, x1_px, py_end))

            margin_px = int(MS_LANDSCAPE_MARGIN_PT * scale)
            content_w = max(1, page_width_px - 2 * margin_px)
            if strip_raw.width > 0:
                ratio = content_w / strip_raw.width
                new_h = max(1, int(strip_raw.height * ratio))
                strip_raw = strip_raw.resize((content_w, new_h), Image.LANCZOS)
            strip = Image.new("RGB", (page_width_px, strip_raw.height), (255, 255, 255))
            strip.paste(strip_raw, (margin_px, 0))
        else:
            l_px, r_px, t_px = insets_for_strip(y_start, page_h_pt, scale)

            w = img.width
            if l_px + r_px >= w - 4:
                x0, x1 = 0, w
            else:
                x0 = min(l_px, w - 2)
                x1 = max(x0 + 1, w - r_px)

            band_h = py_end - py_start
            t_eff = min(t_px, max(0, band_h - 2))
            py_a = py_start + t_eff
            if py_a >= py_end:
                py_a = py_start

            strip = img.crop((x0, py_a, x1, py_end))

            if strip.width > page_width_px:
                ratio = page_width_px / strip.width
                new_h = int(strip.height * ratio)
                strip = strip.resize((page_width_px, new_h), Image.LANCZOS)

        if current_qnum is not None and qnum != current_qnum:
            strips.append(Image.new("RGB", (page_width_px, separator_height), (255, 255, 255)))

        strips.append(strip)
        current_qnum = qnum

    return strips


def section_title_strip(label: str) -> Image.Image:
    """Single-line centered strip (e.g. paper id) before a mark scheme block."""
    scale, page_width_px, _ = scale_and_page_dims()
    h = int(22 * scale)
    img = Image.new("RGB", (page_width_px, h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    size_px = max(10, int(10 * scale))
    font = pil_font(size_px)
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (page_width_px - tw) // 2
    y = max(0, (h - th) // 2)
    draw.text((x, y), label, fill=(70, 70, 70), font=font)
    return img


def create_mcq_answer_strips(answers: dict, requested_questions: list) -> list:
    """Return PIL image strips: bold 'Multiple Choice Answers' headline, then one row per answer."""
    scale, page_width_px, _ = scale_and_page_dims()
    found = [(q, answers[q]) for q in requested_questions if q in answers]
    if not found:
        return []
    headline_size = max(12, int(14 * scale))
    font_bold = pil_font_bold(headline_size)
    head_h = int(10 * scale) + headline_size
    headline = Image.new("RGB", (page_width_px, head_h), (255, 255, 255))
    hdraw = ImageDraw.Draw(headline)
    title = "Multiple Choice Answers"
    hb = hdraw.textbbox((0, 0), title, font=font_bold)
    th = hb[3] - hb[1]
    left_x = int(50 * scale)
    hdraw.text(
        (left_x, max(0, (head_h - th) // 2)),
        title,
        fill=(0, 0, 0),
        font=font_bold,
    )
    strips = [headline]

    row_h = max(1, int(20 * scale))
    font_size = max(10, int(11 * scale))
    font = pil_font(font_size)
    for qnum, letter in found:
        strip = Image.new("RGB", (page_width_px, row_h), (255, 255, 255))
        draw = ImageDraw.Draw(strip)
        y_txt = max(0, (row_h - font_size) // 2)
        draw.text((int(50 * scale), y_txt), f"Q{qnum}: {letter}", fill=(0, 0, 0), font=font)
        strips.append(strip)
    return strips


def layout_strips_to_pdf(strips, output_path, header_label: str | None = None):
    """Flow strips onto A4 pages."""
    hl = (header_label or "").strip() or None
    scale, page_width_px, page_height_px = scale_and_page_dims()
    margin_px = int(15 * scale)

    current_paper_label: str | None = None
    for _item in strips:
        if isinstance(_item, str):
            current_paper_label = _item
            break

    header_px = header_band_px(hl, scale, has_paper_label=(hl is not None))
    usable_height = page_height_px - 2 * margin_px - header_px
    initial_y_cursor = margin_px + header_px

    def new_canvas():
        img = Image.new("RGB", (page_width_px, page_height_px), (255, 255, 255))
        if hl and header_px > 0:
            draw_page_header_pil(img, hl, current_paper_label, header_px, scale)
        elif not hl and current_paper_label and header_px > 0:
            draw_exam_label_pil(img, current_paper_label, header_px, scale)
        return img, initial_y_cursor

    def _redraw_header(page_img: Image.Image) -> None:
        draw = ImageDraw.Draw(page_img)
        draw.rectangle([0, 0, page_width_px, margin_px + header_px], fill=(255, 255, 255))
        if hl and header_px > 0:
            draw_page_header_pil(page_img, hl, current_paper_label, header_px, scale)
        elif not hl and current_paper_label and header_px > 0:
            draw_exam_label_pil(page_img, current_paper_label, header_px, scale)

    pages = []
    current_page, y_cursor = new_canvas()

    for item in strips:
        if isinstance(item, str):
            current_paper_label = item
            if y_cursor == initial_y_cursor:
                _redraw_header(current_page)
            else:
                lbl_strip = section_title_strip(item)
                sh = lbl_strip.height
                if y_cursor + sh > page_height_px - margin_px:
                    pages.append(current_page)
                    current_page, y_cursor = new_canvas()
                else:
                    current_page.paste(lbl_strip, (h_center_x(lbl_strip.width, page_width_px), y_cursor))
                    y_cursor += sh
            continue

        strip = item
        sh = strip.height

        if y_cursor + sh > page_height_px - margin_px:
            if sh > usable_height:
                src_y = 0
                remaining = sh
                while remaining > 0:
                    available = page_height_px - margin_px - y_cursor
                    if available < 40:
                        pages.append(current_page)
                        current_page, y_cursor = new_canvas()
                        available = page_height_px - margin_px - y_cursor

                    chunk_h = min(remaining, available)
                    chunk = strip.crop((0, src_y, strip.width, src_y + chunk_h))
                    current_page.paste(chunk, (h_center_x(chunk.width, page_width_px), y_cursor))
                    y_cursor += chunk_h
                    src_y += chunk_h
                    remaining -= chunk_h

                    if remaining > 0:
                        pages.append(current_page)
                        current_page, y_cursor = new_canvas()
                continue
            else:
                pages.append(current_page)
                current_page, y_cursor = new_canvas()

        current_page.paste(strip, (h_center_x(strip.width, page_width_px), y_cursor))
        y_cursor += sh

    pages.append(current_page)

    print(f"  Assembling {len(pages)} output page(s)...")
    out_doc = fitz.open()
    for page_img in pages:
        buf = io.BytesIO()
        page_img.save(buf, format="JPEG", quality=92)
        buf.seek(0)
        page = out_doc.new_page(width=A4_WIDTH_PT, height=A4_HEIGHT_PT)
        page.insert_image(fitz.Rect(0, 0, A4_WIDTH_PT, A4_HEIGHT_PT), stream=buf.read())

    out_doc.save(output_path, deflate=True, garbage=4)
    out_doc.close()
    print(f"  Saved: {output_path}")


def render_regions_to_pdf(doc, regions, output_path, header_label: str | None = None):
    """Render regions and assemble into an A4 output PDF."""
    strips = collect_strips_from_regions(doc, regions)
    layout_strips_to_pdf(strips, output_path, header_label)


def create_mcq_answers_pdf(
    answers,
    requested_questions,
    output_path,
    header_label: str | None = None,
    section_label: str | None = None,
):
    """Create a simple PDF listing MCQ answers."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas

    from .config import EXAM_LABEL_FONT_PT

    c = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4

    def draw_exam_line():
        if header_label:
            c.setFont("Helvetica", EXAM_LABEL_FONT_PT)
            w = stringWidth(header_label, "Helvetica", EXAM_LABEL_FONT_PT)
            from_top = EXAM_LABEL_FONT_PT + 17
            c.drawString((width - w) / 2, height - from_top, header_label)

    draw_exam_line()
    _shift = max(0, EXAM_LABEL_FONT_PT - 11)
    _extra = 0
    if section_label:
        c.setFont("Helvetica-Bold", 11)
        sw = stringWidth(section_label, "Helvetica-Bold", 11)
        c.drawString((width - sw) / 2, height - (42 + _shift), section_label)
        _extra = 22
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - (58 + _shift + _extra), "Multiple Choice Answers")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - (78 + _shift + _extra), "Paper 2 Multiple Choice (Extended)")

    y = height - (118 + _shift + _extra)
    c.setFont("Helvetica", 13)

    for qnum in requested_questions:
        if qnum in answers:
            c.setFont("Helvetica", 13)
            c.drawString(50, y, f"Q{qnum}:")
            c.setFont("Helvetica-Bold", 13)
            c.drawString(95, y, answers[qnum])
            y -= 28
            if y < 60:
                c.showPage()
                draw_exam_line()
                y = height - 60

    c.save()
    print(f"  Saved: {output_path}")
