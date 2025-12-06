# pdf_utils.py
import io
from pdfrw import PdfReader, PdfWriter, PageMerge
from reportlab.pdfgen import canvas

def get_page_size_from_pdf_bytes(pdf_bytes):
    trailer = PdfReader(fdata=pdf_bytes)
    page = trailer.pages[0]
    mediabox = page.MediaBox
    width = float(mediabox[2]) - float(mediabox[0])
    height = float(mediabox[3]) - float(mediabox[1])
    return width, height

def create_overlay_pdf_bytes(width, height, texts_with_positions, font_name="Helvetica-Bold", font_size=12):
    """
    texts_with_positions: list of tuples [(x_pt, y_pt, texto), ...]
    Coordinates are in points (1 pt = 1/72 inch), origin is lower-left.
    """
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(width, height))
    c.setFont(font_name, font_size)
    # allow multi-line text: split by \n and increment y
    for x, y, text, size in texts_with_positions:
        if size is not None:
            c.setFont(font_name, size)
        else:
            c.setFont(font_name, font_size)
        lines = str(text).split("\n")
        leading = (c._fontsize or font_size) + 2
        for i, line in enumerate(lines):
            c.drawString(x, y - i * leading, line)
    c.save()
    packet.seek(0)
    return packet.read()

def merge_overlay_on_template(template_pdf_bytes, overlay_pdf_bytes):
    template = PdfReader(fdata=template_pdf_bytes)
    overlay = PdfReader(fdata=overlay_pdf_bytes)
    for page_t, page_o in zip(template.pages, overlay.pages):
        merger = PageMerge(page_t)
        merger.add(page_o).render()
    out_buf = io.BytesIO()
    PdfWriter(out_buf, trailer=template).write()
    out_buf.seek(0)
    return out_buf.read()

def fill_pdf(template_pdf_bytes, texts_with_positions, font_name="Helvetica-Bold", default_font_size=12):
    # compute page size from template
    width, height = get_page_size_from_pdf_bytes(template_pdf_bytes)
    # ensure font size is in tuples; texts_with_positions entries are (x,y,text,size)
    overlay = create_overlay_pdf_bytes(width, height, texts_with_positions, font_name, default_font_size)
    result_bytes = merge_overlay_on_template(template_pdf_bytes, overlay)
    return result_bytes
