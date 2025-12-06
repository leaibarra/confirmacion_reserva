import streamlit as st
import re
from pdf_utils import fill_pdf, get_page_size_from_pdf_bytes

st.set_page_config(page_title="Confirmación de Reserva", layout="centered")

st.title("Generador de Confirmación de Reserva (PDF plantilla fija)")

# ======================
#       PLANTILLA
# ======================

TEMPLATE_PATH = "templates/reserva_base.pdf"

with open(TEMPLATE_PATH, "rb") as f:
    template_bytes = f.read()

st.info(f"Usando la plantilla fija: {TEMPLATE_PATH}")

page_width, page_height = get_page_size_from_pdf_bytes(template_bytes)

# ======================
#   HELPERS
# ======================

def extract_int(val):
    if not val:
        return None
    cleaned = re.sub(r"[^\d]", "", val)
    if cleaned == "":
        return None
    return int(cleaned)

def format_money(n):
    if n is None:
        return ""
    return "$" + f"{n:,}".replace(",", ".")

# ======================
# PARSER DEL WHATSAPP
# ======================

def parse_whatsapp_text(raw_text):
    out = {}

    # Limpieza básica
    txt = raw_text.replace("•", "\n").replace("*", "\n").replace("\r", "\n")
    txt = "\n".join([l.strip() for l in txt.splitlines() if l.strip()])

    def find(p, default=""):
        m = re.search(p, txt, re.IGNORECASE)
        return m.group(1).strip() if m else default

    # Fechas y datos generales
    out["check_in"] = find(r"Check[- ]?in[:\s]*([0-3]?\d\/[01]?\d\/\d{4})")
    out["check_out"] = find(r"Check[- ]?out[:\s]*([0-3]?\d\/[01]?\d\/\d{4})")
    out["noches"] = find(r"Cantidad de noches[:\s]*([0-9]+)")
    out["personas"] = find(r"Cantidad de personas[:\s]*([0-9]+)")
    out["habitacion"] = find(r"Habitación[:\s]*([^\n\r]+)")
    out["pension"] = find(r"Pensión[:\s]*([^\n\r]+)")

    # Montos
    out["total"] = find(r"Total de la estad[ií]a[:\s]*\$?\s*([\d\.\,]+)")
    out["senal"] = find(r"Se[nñ]a.*[:\s]*\$?\s*([\d\.\,]+)")
    out["saldo"] = find(r"Saldo restante.*[:\s]*\$?\s*([\d\.\,]+)")

    # Email + Dirección
    out["email"] = find(r"Email[:\s]*([^\s]+)")
    out["direccion"] = find(r"Direcci[oó]n[:\s]*([^\n\r]+)")

    # ================
    # TELÉFONO FIABLE
    # ================

    # Buscar "Teléfono", "Telefono", "Teléfono de contacto", etc.
    tel_match = re.search(
        r"Tel[eé]fono(?: de contacto)?[:\s]*([\d\-\s\(\)]{7,20})",
        txt,
        re.IGNORECASE
    )

    telefono = ""

    if tel_match:
        telefono = tel_match.group(1).strip()
    else:
        # Si no lo encuentra por etiqueta, busco el primer número largo
        nums = re.findall(r"\d{7,12}", txt)
        if nums:
            telefono = nums[0]

    # No convertir teléfono = DNI por error
    if telefono == out.get("dni", ""):
        # buscar otro número distinto al dni
        nums = [n for n in re.findall(r"\d{7,12}", txt) if n != telefono]
        if nums:
            telefono = nums[0]

    out["telefono"] = telefono


    # Detectar huéspedes
    guests = re.findall(
        r"Nombre y apellido[:\s]*([A-Za-zÁÉÍÓÚáéíóúñÑ\.\s]+?)\n.*?DNI[:\s]*([0-9]{6,10})",
        txt,
        re.IGNORECASE
    )

    if guests:
        out["nombre"] = guests[0][0].strip()
        out["dni"] = guests[0][1]
    else:
        out["nombre"] = find(r"Nombre y apellido[:\s]*([A-Za-zÁÉÍÓÚáéíóúñÑ\.\s]+)")
        out["dni"] = find(r"DNI[:\s]*([0-9]{6,10})")

    # Acompañante
    acomp = []
    for nm, dn in guests[1:]:
        acomp.append({"nombre": nm.strip(), "dni": dn.strip()})

    out["acompanantes"] = acomp

    return out

# ======================
#   ENTRADA DE TEXTO
# ======================

st.subheader("Pegá el texto del WhatsApp:")

raw = st.text_area("Texto original", height=250)
parsed = parse_whatsapp_text(raw)

# ======================
#   CAMPOS EDITABLES
# ======================

st.subheader("Datos detectados:")

nombre = st.text_input("Nombre", parsed.get("nombre", ""))
dni = st.text_input("DNI", parsed.get("dni", ""))
telefono = st.text_input("Teléfono", parsed.get("telefono", ""))
direccion = st.text_input("Dirección", parsed.get("direccion", ""))
email = st.text_input("Email", parsed.get("email", ""))

checkin = st.text_input("Check-in", parsed.get("check_in", ""))
checkout = st.text_input("Check-out", parsed.get("check_out", ""))
noches = st.text_input("Noches", parsed.get("noches", ""))
personas = st.text_input("Personas", parsed.get("personas", ""))
habitacion = st.text_input("Habitación", parsed.get("habitacion", ""))
pension = st.text_input("Pensión", parsed.get("pension", ""))

# Montos normalizados (con cálculo automático)
total_raw = parsed.get("total", "")
senal_raw = parsed.get("senal", "")
saldo_raw = parsed.get("saldo", "")

total_int = extract_int(total_raw)
senal_int = extract_int(senal_raw)
saldo_int = extract_int(saldo_raw)

# Cálculos automáticos
if total_int and not senal_int:
    senal_int = total_int // 2
if total_int and senal_int and not saldo_int:
    saldo_int = total_int - senal_int

total_str = format_money(total_int)
senal_str = format_money(senal_int)
saldo_str = format_money(saldo_int)

total = st.text_input("Total", total_str)
senal = st.text_input("Seña", senal_str)
saldo = st.text_input("Saldo", saldo_str)

# Acompañante
acomp = parsed.get("acompanantes", [])
if acomp:
    nombre_acomp = st.text_input("Acompañante - Nombre", acomp[0]["nombre"])
    dni_acomp = st.text_input("Acompañante - DNI", acomp[0]["dni"])
else:
    nombre_acomp = st.text_input("Acompañante - Nombre", "")
    dni_acomp = st.text_input("Acompañante - DNI", "")

# ======================
# POSICIONES FIJAS
# ======================

positions = {
    "check_in": (145, 601, 12),
    "check_out": (153, 584, 12),
    "noches": (215, 567, 12),
    "personas": (230, 549, 12),
    "habitacion": (157, 532, 12),
    "pension": (142, 515, 12),

    "total": (207, 463, 12),
    "senal": (219, 445, 12),
    "saldo": (336, 429, 12),

    "nombre": (205, 377, 12),
    "nombre2": (123, 664, 12),
    "dni": (106, 360, 12),
    "telefono": (226, 342, 12),
    "direccion": (153, 325, 12),
    "email": (123, 308, 12),

    "acomp_nombre": (202, 273, 12),
    "acomp_dni": (422, 273, 12),
}

# ======================
#   GENERAR PDF
# ======================

if st.button("Generar PDF"):

    # Si teléfono == dni → buscar otro
    if re.sub(r"\D", "", telefono) == re.sub(r"\D", "", dni):
        nums = re.findall(r"\d{7,12}", raw)
        tel2 = ""
        for n in nums:
            if n != dni:
                tel2 = n
                break
        if tel2:
            telefono = tel2

    texts = [
        (positions["check_in"][0], positions["check_in"][1], checkin, positions["check_in"][2]),
        (positions["check_out"][0], positions["check_out"][1], checkout, positions["check_out"][2]),
        (positions["noches"][0], positions["noches"][1], noches, positions["noches"][2]),
        (positions["personas"][0], positions["personas"][1], personas, positions["personas"][2]),
        (positions["habitacion"][0], positions["habitacion"][1], habitacion, positions["habitacion"][2]),
        (positions["pension"][0], positions["pension"][1], pension, positions["pension"][2]),

        (positions["total"][0], positions["total"][1], total, positions["total"][2]),
        (positions["senal"][0], positions["senal"][1], senal, positions["senal"][2]),
        (positions["saldo"][0], positions["saldo"][1], saldo, positions["saldo"][2]),

        # Huésped
        (positions["nombre"][0], positions["nombre"][1], nombre, positions["nombre"][2]),
        (positions["nombre2"][0], positions["nombre2"][1], nombre, positions["nombre2"][2]),
        (positions["dni"][0], positions["dni"][1], dni, positions["dni"][2]),
        (positions["telefono"][0], positions["telefono"][1], telefono, positions["telefono"][2]),
        (positions["direccion"][0], positions["direccion"][1], direccion, positions["direccion"][2]),
        (positions["email"][0], positions["email"][1], email, positions["email"][2]),

        # Acompañante
        (positions["acomp_nombre"][0], positions["acomp_nombre"][1], nombre_acomp, positions["acomp_nombre"][2]),
        (positions["acomp_dni"][0], positions["acomp_dni"][1], dni_acomp, positions["acomp_dni"][2]),
    ]

    result = fill_pdf(template_bytes, texts)

    st.success("PDF generado correctamente.")
    st.download_button("Descargar PDF", result, file_name="confirmacion_reserva.pdf", mime="application/pdf")
