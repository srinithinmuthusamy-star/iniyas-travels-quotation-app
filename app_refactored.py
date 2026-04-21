from datetime import date
from io import BytesIO
from pathlib import Path
import json

import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle


PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 18 * mm
RIGHT_MARGIN = 18 * mm
TOP_MARGIN = 18 * mm
BOTTOM_MARGIN = 18 * mm
CONTENT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN
SECTION_GAP = 8

LINE_COLOR = colors.HexColor("#2E3A59")
FILL_COLOR = colors.HexColor("#F5F7FB")
ACCENT_COLOR = colors.HexColor("#0B6E4F")
TEXT_COLOR = colors.HexColor("#1B1F23")
MUTED_TEXT = colors.HexColor("#5B6575")
COUNTER_FILE = Path(__file__).with_name("document_counters.json")


def format_currency(value: float) -> str:
    return f"Rs. {value:,.2f}"


def load_counters() -> dict:
    default_data = {"quotation": 0, "invoice": 0}
    if COUNTER_FILE.exists():
        try:
            data = json.loads(COUNTER_FILE.read_text(encoding="utf-8"))
            return {
                "quotation": int(data.get("quotation", 0)),
                "invoice": int(data.get("invoice", 0)),
            }
        except Exception:
            return default_data
    return default_data


def save_counters(data: dict) -> None:
    try:
        COUNTER_FILE.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass


def get_next_document_number(doc_type: str) -> str:
    counters = load_counters()
    if doc_type == "Quotation":
        counters["quotation"] += 1
        save_counters(counters)
        return f"QT-{counters['quotation']:04d}"
    counters["invoice"] += 1
    save_counters(counters)
    return f"INV-{counters['invoice']:04d}"


def draw_section_title(pdf: canvas.Canvas, x: float, y: float, width: float, title: str) -> float:
    title_height = 18
    pdf.setFillColor(ACCENT_COLOR)
    pdf.roundRect(x, y - title_height, width, title_height, 4, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(x + 8, y - 12.5, title.upper())
    return y - title_height


def draw_box(pdf: canvas.Canvas, x: float, y: float, width: float, height: float) -> None:
    pdf.setStrokeColor(LINE_COLOR)
    pdf.setLineWidth(0.9)
    pdf.setFillColor(colors.white)
    pdf.roundRect(x, y - height, width, height, 6, stroke=1, fill=1)


def draw_key_value_grid(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    width: float,
    title: str,
    rows: list[tuple[str, str, str, str]],
) -> float:
    title_bottom = draw_section_title(pdf, x, y, width, title)
    row_height = 24
    body_height = len(rows) * row_height
    draw_box(pdf, x, title_bottom, width, body_height)

    half_width = width / 2
    pdf.setStrokeColor(colors.HexColor("#D8DFEA"))
    pdf.setLineWidth(0.6)

    for index in range(1, len(rows)):
        row_y = title_bottom - index * row_height
        pdf.line(x, row_y, x + width, row_y)

    pdf.line(x + half_width, title_bottom, x + half_width, title_bottom - body_height)

    for index, (left_label, left_value, right_label, right_value) in enumerate(rows):
        text_y = title_bottom - (index * row_height) - 16

        pdf.setFillColor(MUTED_TEXT)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(x + 10, text_y, left_label)
        pdf.drawString(x + half_width + 10, text_y, right_label)

        pdf.setFillColor(TEXT_COLOR)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(x + 78, text_y, left_value)
        pdf.drawString(x + half_width + 78, text_y, right_value)

    return title_bottom - body_height - SECTION_GAP


def draw_table_section(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    width: float,
    title: str,
    data: list[list[str]],
) -> float:
    title_bottom = draw_section_title(pdf, x, y, width, title)
    table = Table(
        data,
        colWidths=[width * 0.12, width * 0.58, width * 0.30],
        rowHeights=[24] + [22] * (len(data) - 1),
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDEEE7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), TEXT_COLOR),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (1, 0), (1, -1), "LEFT"),
                ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.8, LINE_COLOR),
                ("BACKGROUND", (0, 1), (-1, -2), colors.white),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    _, table_height = table.wrap(width, 0)
    draw_box(pdf, x, title_bottom, width, table_height)
    table.drawOn(pdf, x, title_bottom - table_height)
    return title_bottom - table_height - SECTION_GAP


def draw_paragraph_section(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    width: float,
    title: str,
    lines: list[str],
) -> float:
    styles = getSampleStyleSheet()
    style = styles["BodyText"]
    style.fontName = "Helvetica"
    style.fontSize = 8.6
    style.leading = 12
    style.textColor = TEXT_COLOR
    style.spaceAfter = 0

    title_bottom = draw_section_title(pdf, x, y, width, title)
    paragraphs = [Paragraph(f"{i}. {line}", style) for i, line in enumerate(lines, start=1)]

    available_width = width - 16
    paragraph_heights = [paragraph.wrap(available_width, PAGE_HEIGHT)[1] for paragraph in paragraphs]
    body_height = sum(paragraph_heights) + 16

    draw_box(pdf, x, title_bottom, width, body_height)

    current_y = title_bottom - 10
    for paragraph, paragraph_height in zip(paragraphs, paragraph_heights):
        paragraph.drawOn(pdf, x + 8, current_y - paragraph_height)
        current_y -= paragraph_height + 2

    return title_bottom - body_height - SECTION_GAP


def estimate_paragraph_section_height(lines: list[str], width: float) -> float:
    styles = getSampleStyleSheet()
    style = styles["BodyText"]
    style.fontName = "Helvetica"
    style.fontSize = 8.6
    style.leading = 12
    style.textColor = TEXT_COLOR
    style.spaceAfter = 0

    available_width = width - 16
    paragraphs = [Paragraph(f"{i}. {line}", style) for i, line in enumerate(lines, start=1)]
    paragraph_heights = [paragraph.wrap(available_width, PAGE_HEIGHT)[1] for paragraph in paragraphs]
    body_height = sum(paragraph_heights) + 16
    title_height = 18
    return title_height + body_height + SECTION_GAP


def estimate_payment_section_height(payment_rows: list[tuple[str, str]]) -> float:
    title_height = 18
    row_height = 24
    body_height = len(payment_rows) * row_height
    return title_height + body_height + SECTION_GAP


def ensure_space(current_y: float, required_height: float, payload: dict, pdf: canvas.Canvas) -> float:
    if current_y - required_height < BOTTOM_MARGIN + 18:
        return start_new_page(pdf, payload)
    return current_y


def start_new_page(pdf: canvas.Canvas, payload: dict) -> float:
    pdf.showPage()
    return draw_header(
        pdf,
        payload["doc_type"],
        payload["doc_number"],
        payload["doc_date"],
        payload["logo_path"],
    )


def draw_payment_and_signature(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    width: float,
    payment_rows: list[tuple[str, str]],
) -> float:
    left_width = width * 0.58
    right_width = width - left_width - 12

    payment_title_bottom = draw_section_title(pdf, x, y, left_width, "Payment Details")
    row_height = 24
    payment_height = len(payment_rows) * row_height
    draw_box(pdf, x, payment_title_bottom, left_width, payment_height)

    pdf.setStrokeColor(colors.HexColor("#D8DFEA"))
    pdf.setLineWidth(0.6)
    label_col = left_width * 0.34
    pdf.line(x + label_col, payment_title_bottom, x + label_col, payment_title_bottom - payment_height)

    for index in range(1, len(payment_rows)):
        row_y = payment_title_bottom - index * row_height
        pdf.line(x, row_y, x + left_width, row_y)

    for index, (label, value) in enumerate(payment_rows):
        text_y = payment_title_bottom - (index * row_height) - 16
        pdf.setFont("Helvetica-Bold", 9)
        pdf.setFillColor(MUTED_TEXT)
        pdf.drawString(x + 10, text_y, label)
        pdf.setFont("Helvetica", 9)
        pdf.setFillColor(TEXT_COLOR)
        pdf.drawString(x + label_col + 10, text_y, value)

    sign_x = x + left_width + 12
    sign_title_bottom = draw_section_title(pdf, sign_x, y, right_width, "Authorized Signatory")
    sign_height = payment_height
    draw_box(pdf, sign_x, sign_title_bottom, right_width, sign_height)

    line_y = sign_title_bottom - sign_height + 34
    pdf.setStrokeColor(LINE_COLOR)
    pdf.line(sign_x + 18, line_y, sign_x + right_width - 18, line_y)
    pdf.setFillColor(MUTED_TEXT)
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(sign_x + (right_width / 2), line_y - 16, "For Iniyas Travels")

    return min(payment_title_bottom - payment_height, sign_title_bottom - sign_height) - SECTION_GAP


def draw_header(pdf: canvas.Canvas, doc_type: str, doc_number: str, doc_date: date, logo_path: str) -> float:
    header_height = 88
    x = LEFT_MARGIN
    y = PAGE_HEIGHT - TOP_MARGIN

    pdf.setFillColor(FILL_COLOR)
    pdf.setStrokeColor(LINE_COLOR)
    pdf.setLineWidth(1)
    pdf.roundRect(x, y - header_height, CONTENT_WIDTH, header_height, 8, stroke=1, fill=1)

    logo_box_width = 90
    logo_box_height = 52
    logo_box_x = x + CONTENT_WIDTH - logo_box_width - 12
    logo_box_y = y - 16 - logo_box_height

    pdf.setFillColor(TEXT_COLOR)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(x + 14, y - 24, "INIYAS TRAVELS")

    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(MUTED_TEXT)
    pdf.drawString(x + 14, y - 40, "GN Chetty Road, T. Nagar, Chennai - 600017")
    pdf.drawString(x + 14, y - 54, "Phone: +91 95003 50141")
    pdf.drawString(x + 14, y - 68, "Email: iniyastravels@gmail.com")

    right_edge = logo_box_x - 14

    pdf.setFont("Helvetica-Bold", 16)
    pdf.setFillColor(ACCENT_COLOR)
    pdf.drawRightString(right_edge, y - 24, doc_type.upper())

    label = "Quotation No" if doc_type == "Quotation" else "Invoice No"
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(TEXT_COLOR)
    pdf.drawRightString(right_edge, y - 42, f"{label}: {doc_number}")
    pdf.drawRightString(right_edge, y - 56, f"Date: {doc_date.strftime('%d-%m-%Y')}")

    logo_file = Path(logo_path).expanduser() if logo_path else None
    if logo_file and logo_file.exists() and logo_file.is_file():
        try:
            logo = ImageReader(str(logo_file))
            img_width, img_height = logo.getSize()

            padding = 4
            max_width = logo_box_width - (padding * 2)
            max_height = logo_box_height - (padding * 2)

            scale = min(max_width / img_width, max_height / img_height)
            draw_width = img_width * scale
            draw_height = img_height * scale

            draw_x = logo_box_x + (logo_box_width - draw_width) / 2
            draw_y = logo_box_y + (logo_box_height - draw_height) / 2

            pdf.drawImage(
                logo,
                draw_x,
                draw_y,
                width=draw_width,
                height=draw_height,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            pass

    return y - header_height - 12


def build_document_pdf(payload: dict) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(f"{payload['doc_type']}_{payload['doc_number']}")

    current_y = draw_header(
        pdf,
        payload["doc_type"],
        payload["doc_number"],
        payload["doc_date"],
        payload["logo_path"],
    )

    customer_rows = [
        ("Customer", payload["customer_name"], "Contact", payload["contact"]),
        ("Email", payload["customer_email"], "Prepared By", payload["prepared_by"]),
    ]
    current_y = ensure_space(current_y, 18 + (24 * len(customer_rows)) + SECTION_GAP, payload, pdf)
    current_y = draw_key_value_grid(pdf, LEFT_MARGIN, current_y, CONTENT_WIDTH, "Customer Details", customer_rows)

    trip_rows = [
        ("Pickup", payload["pickup"], "Drop", payload["drop"]),
        ("Travel Dates", payload["travel_dates"], "Duration", payload["duration_label"]),
        ("Vehicle", payload["vehicle"], "Trip Type", payload["trip_type"]),
    ]
    current_y = ensure_space(current_y, 18 + (24 * len(trip_rows)) + SECTION_GAP, payload, pdf)
    current_y = draw_key_value_grid(pdf, LEFT_MARGIN, current_y, CONTENT_WIDTH, "Trip Details", trip_rows)

    charge_table_height = 18 + (24 + (22 * max(len(payload["charges_table"]) - 1, 0))) + SECTION_GAP
    current_y = ensure_space(current_y, charge_table_height, payload, pdf)
    current_y = draw_table_section(pdf, LEFT_MARGIN, current_y, CONTENT_WIDTH, "Charges", payload["charges_table"])

    footer_reserve = BOTTOM_MARGIN + 20
    payment_section_height = estimate_payment_section_height(payload["payment_rows"])

    if payload["doc_type"] == "Quotation" and payload["terms"]:
        terms_section_height = estimate_paragraph_section_height(payload["terms"], CONTENT_WIDTH)
        current_y = ensure_space(current_y, terms_section_height + payment_section_height + footer_reserve, payload, pdf)

        current_y = draw_paragraph_section(
            pdf,
            LEFT_MARGIN,
            current_y,
            CONTENT_WIDTH,
            "Terms & Conditions",
            payload["terms"],
        )

    current_y = ensure_space(current_y, payment_section_height + footer_reserve, payload, pdf)
    current_y = draw_payment_and_signature(pdf, LEFT_MARGIN, current_y, CONTENT_WIDTH, payload["payment_rows"])

    footer_y = BOTTOM_MARGIN
    pdf.setStrokeColor(colors.HexColor("#D8DFEA"))
    pdf.line(LEFT_MARGIN, footer_y + 12, PAGE_WIDTH - RIGHT_MARGIN, footer_y + 12)
    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(MUTED_TEXT)

    if payload["doc_type"] == "Invoice":
        pdf.drawString(LEFT_MARGIN, footer_y, f"Total Invoice Value: {format_currency(payload['total_amount'])}")
        pdf.drawRightString(PAGE_WIDTH - RIGHT_MARGIN, footer_y, "This is a computer-generated invoice.")
    else:
        pdf.drawString(LEFT_MARGIN, footer_y, "Thank you for choosing Iniyas Travels.")

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


st.set_page_config(page_title="Iniyas Travels Billing", layout="wide")
st.title("Iniyas Travels Quotation / Invoice Generator")
st.caption("Generate professional quotation and invoice PDFs with serial document numbers.")

default_logo = Path(__file__).with_name("logo.jpeg")

doc_type = st.selectbox("Document Type", ["Quotation", "Invoice"])

if "current_doc_number" not in st.session_state:
    st.session_state.current_doc_number = get_next_document_number(doc_type)

if "last_doc_type" not in st.session_state:
    st.session_state.last_doc_type = doc_type

if st.session_state.last_doc_type != doc_type:
    st.session_state.current_doc_number = get_next_document_number(doc_type)
    st.session_state.last_doc_type = doc_type

with st.form("billing_form"):
    left_col, right_col = st.columns(2)

    with left_col:
        st.subheader("Document")
        doc_number = st.text_input("Document Number", value=st.session_state.current_doc_number)
        doc_date = st.date_input("Document Date", value=date.today())

        st.subheader("Customer")
        customer_name = st.text_input("Customer Name", value="Mr. Prabu Devan")
        contact = st.text_input("Contact Number", value="+91 95003 50141")
        customer_email = st.text_input("Customer Email", value="iniyas@example.com")
        prepared_by = st.text_input("Prepared By", value="Iniyas Travels")

        st.subheader("Trip")
        pickup = st.text_input("Pickup Location", value="Chennai")
        drop = st.text_input("Drop Location", value="Kodaikanal")
        start_date = st.date_input("Start Date", value=date.today())
        end_date = st.date_input("End Date", value=date.today())
        vehicle = st.text_input("Vehicle", value="Toyota Etios")
        trip_type = st.selectbox("Trip Type", ["Round Trip", "One Way"])

    with right_col:
        st.subheader("Branding")
        logo_path = st.text_input("Logo Path", value=str(default_logo) if default_logo.exists() else "")

        st.subheader("Charges")
        base_fare = st.number_input("Base Fare", min_value=0.0, value=13800.0, step=100.0)
        driver_bata = st.number_input("Driver Bata", min_value=0.0, value=1600.0, step=100.0)
        toll_charges = st.number_input("Toll Charges", min_value=0.0, value=600.0, step=100.0)
        hill_charges = st.number_input("Hill Charges", min_value=0.0, value=1000.0, step=100.0)
        parking_charges = st.number_input("Parking", min_value=0.0, value=0.0, step=100.0)
        state_taxi = st.number_input("State Taxi", min_value=0.0, value=0.0, step=100.0)
        hour_charge = st.number_input("Hour Charge", min_value=0.0, value=0.0, step=100.0)
        extra_hours = st.number_input("Extra Hours", min_value=0.0, value=0.0, step=100.0)
        extra_km = st.number_input("Extra KM", min_value=0.0, value=0.0, step=100.0)
        permit_charges = st.number_input("Permit / Parking Charges", min_value=0.0, value=0.0, step=100.0)

        st.subheader("Payment")
        bank_name = st.text_input("Bank Name", value="State Bank of India")
        account_name = st.text_input("Account Name", value="Iniyas Travels")
        account_number = st.text_input("Account Number", value="33020794379")
        ifsc = st.text_input("IFSC Code", value="SBIN0012786")
        upi_id = st.text_input("UPI ID", value="8667739634@upi")

    terms_text = ""
    if doc_type == "Quotation":
        terms_text = st.text_area(
            "Terms & Conditions",
            value=(
                "Toll, parking, permit, and interstate taxes are extra unless specifically mentioned.\n"
                "Driver bata is included only if shown in the document.\n"
                "Any extra usage beyond agreed itinerary will be charged additionally.\n"
                "Advance payment is required to confirm the booking.\n"
                "Rates are subject to change during peak dates if not confirmed in advance."
            ),
            height=150,
        )

    submitted = st.form_submit_button("Generate PDF", use_container_width=True)

if submitted:
    if end_date < start_date:
        st.error("End date cannot be earlier than start date.")
    else:
        duration_days = (end_date - start_date).days + 1

        item_rows = [
            ("Base Fare", base_fare),
            ("Driver Bata", driver_bata),
            ("Toll Charges", toll_charges),
            ("Hill Charges", hill_charges),
            ("Parking", parking_charges),
            ("State Taxi", state_taxi),
            ("Hour Charge", hour_charge),
            ("Extra Hours", extra_hours),
            ("Extra KM", extra_km),
            ("Permit / Parking Charges", permit_charges),
        ]

        filtered_items = [(desc, amount) for desc, amount in item_rows if amount > 0]
        total_amount = sum(amount for _, amount in filtered_items)

        charge_rows = [["S.No", "Description", "Amount"]]
        for index, (desc, amount) in enumerate(filtered_items, start=1):
            charge_rows.append([str(index), desc, format_currency(amount)])
        charge_rows.append(["", "Grand Total", format_currency(total_amount)])

        payload = {
            "doc_type": doc_type,
            "doc_number": doc_number.strip() or st.session_state.current_doc_number,
            "doc_date": doc_date,
            "logo_path": logo_path.strip(),
            "customer_name": customer_name.strip() or "-",
            "contact": contact.strip() or "-",
            "customer_email": customer_email.strip() or "-",
            "prepared_by": prepared_by.strip() or "Iniyas Travels",
            "pickup": pickup.strip() or "-",
            "drop": drop.strip() or "-",
            "travel_dates": f"{start_date.strftime('%d-%m-%Y')} to {end_date.strftime('%d-%m-%Y')}",
            "duration_label": f"{duration_days} Day(s)",
            "vehicle": vehicle.strip() or "-",
            "trip_type": trip_type,
            "charges_table": charge_rows,
            "terms": [line.strip() for line in terms_text.splitlines() if line.strip()],
            "total_amount": total_amount,
            "payment_rows": [
                ("Bank", bank_name.strip() or "-"),
                ("Account Name", account_name.strip() or "-"),
                ("Account Number", account_number.strip() or "-"),
                ("IFSC", ifsc.strip() or "-"),
                ("UPI", upi_id.strip() or "-"),
            ],
        }

        pdf_bytes = build_document_pdf(payload)
        file_prefix = "Quotation" if doc_type == "Quotation" else "Invoice"

        st.success(f"{doc_type} PDF generated successfully.")
        st.download_button(
            label=f"Download {doc_type} PDF",
            data=pdf_bytes,
            file_name=f"{file_prefix}_{payload['doc_number']}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

        st.session_state.current_doc_number = get_next_document_number(doc_type)
