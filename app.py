import streamlit as st
import re
from pdf_utils import fill_pdf, get_page_size_from_pdf_bytes

st.set_page_config(page_title="Confirmación de Reserva | LIMA", page_icon="assets/favicon.ico", layout="wide")

# Inyectar CSS personalizado para gradientes
st.markdown("""
<style>    
    body::after {
        content: '';
        position: fixed;
        bottom: 0;
        right: 0;
        width: 300px;
        height: 300px;
        background: radial-gradient(circle at bottom right, #d4ffaa 0%, transparent 65%);
        pointer-events: none;
        z-index: 0 !important;
    }
    
    [data-testid="stAppViewContainer"] {
        position: relative;
        z-index: 10 !important;
    }

    .lima-logo {
        position: fixed !important;
        top: 8px !important;
        left: 15px !important;
        z-index: 999999 !important;
        font-size: 24px !important;
        font-weight: bold !important;
        display: flex !important;
        gap: -4px !important;
        filter: drop-shadow(0 0 2px rgba(0,0,0,0.8)) drop-shadow(0 0 4px rgba(0,0,0,0.5));
    }

    .lima-logo span:nth-child(1) { 
        color: #007f3f; 
        margin-left: -10px;
        text-shadow: -1px -1px 0 rgba(0,0,0,0.3), 1px -1px 0 rgba(0,0,0,0.3), -1px 1px 0 rgba(0,0,0,0.3), 1px 1px 0 rgba(0,0,0,0.3);
    }
    .lima-logo span:nth-child(2) { 
        color: #5fbf00; 
        margin-left: -63px;
        text-shadow: -1px -1px 0 rgba(0,0,0,0.3), 1px -1px 0 rgba(0,0,0,0.3), -1px 1px 0 rgba(0,0,0,0.3), 1px 1px 0 rgba(0,0,0,0.3);
    }
    .lima-logo span:nth-child(3) { 
        color: #d4ffaa; 
        margin-left: -63px;
        text-shadow: -1px -1px 0 rgba(0,0,0,0.5), 1px -1px 0 rgba(0,0,0,0.5), -1px 1px 0 rgba(0,0,0,0.5), 1px 1px 0 rgba(0,0,0,0.5);
    }

    h1, h2, h3, h4, h5, h6 {
        position: relative;
    }

    h1 {
        text-align: center !important;
    }

    h1 svg, h2 svg, h3 svg, h4 svg, h5 svg, h6 svg {
        display: none;
    }

    h1:hover svg, h2:hover svg, h3:hover svg, h4:hover svg, h5:hover svg, h6:hover svg {
        display: none !important;
    }

    /* Estilos para campos de entrada transparentes */
    input[type="text"] {
        background-color: transparent !important;
        border: none !important;
        border-bottom: 2px solid #888 !important;
        border-image: linear-gradient(to right, #888, transparent) 1 !important;
        padding-bottom: 8px !important;
        color: inherit !important;
        font-size: inherit !important;
    }

    input[type="text"]:focus {
        background-color: transparent !important;
        border: none !important;
        border-bottom: 2px solid #5fbf00 !important;
        border-image: linear-gradient(to right, #5fbf00, transparent) 1 !important;
        box-shadow: none !important;
        outline: none !important;
    }

    input[type="text"]::placeholder {
        color: rgba(255, 255, 255, 0.4) !important;
    }

    /* Remover fondo del contenedor del input */
    [data-testid="stTextInput"] {
        background-color: transparent !important;
    }

    [data-testid="stTextInput"] > div {
        background-color: transparent !important;
    }

    [data-testid="stTextInput"] > div > div {
        background-color: transparent !important;
    }
</style>

<div class="lima-logo">
    <span>L I M A</span><span>L I M A</span><span>L I M A</span>
</div>
""", unsafe_allow_html=True)

st.title("Generador de Confirmación de Reserva")

# ======================
#       PLANTILLA
# ======================

TEMPLATE_PATH = "templates/reserva_base.pdf"

with open(TEMPLATE_PATH, "rb") as f:
    template_bytes = f.read()

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
    out["senal"] = find(r"Se[nñ]a[^:]*[:\s]*\$?\s*([\d\.\,]+)")
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

# Texto fijo por defecto (incluye los 2 saltos de línea al comienzo y las comillas simples tal cual)
_default_raw = "\n\nDatos de la Reserva\n • Check-in: 01/01/2026\n • Check-out: 01/01/2026\n • Cantidad de noches: 3\n • Cantidad de personas: 2\n • Habitación: 1\n • Pensión:  Media pensión\n\nDetalles del Pago\n • Total de la estadía: $\n • Seña recibida (50%): $\n • Saldo restante a abonar en el check-in: "

# Se puede modificar manualmente en el text_area
raw = st.text_area("Texto original", value=_default_raw, height=250)
parsed = parse_whatsapp_text(raw)

# --- Nuevo: sincronizar session_state cuando cambia el texto pegado ---
if "last_raw" not in st.session_state or st.session_state.last_raw != raw:
	# marcar nuevo raw
	st.session_state.last_raw = raw

	# Campos personales / acompañante / reserva
	st.session_state["nombre"] = parsed.get("nombre", "")
	st.session_state["dni"] = parsed.get("dni", "")
	st.session_state["telefono"] = parsed.get("telefono", "")
	st.session_state["direccion"] = parsed.get("direccion", "")
	st.session_state["email"] = parsed.get("email", "")

	acomp = parsed.get("acompanantes", [])
	st.session_state["nombre_acomp"] = acomp[0]["nombre"] if acomp else ""
	st.session_state["dni_acomp"] = acomp[0]["dni"] if acomp else ""

	st.session_state["checkin"] = parsed.get("check_in", "")
	st.session_state["checkout"] = parsed.get("check_out", "")
	st.session_state["noches"] = parsed.get("noches", "")
	st.session_state["personas"] = parsed.get("personas", "")
	st.session_state["habitacion"] = parsed.get("habitacion", "")
	st.session_state["pension"] = parsed.get("pension", "")

# ======================
#   CAMPOS EDITABLES
# ======================

st.subheader("Datos detectados (Se pueden modificar):")

# BLOQUE 1: DATOS PERSONALES Y ACOMPAÑANTE
with st.expander("🫆 Datos Personales y Acompañante", expanded=True):
    st.markdown("**Huésped Principal**")
    row1 = st.columns(5)
    nombre = row1[0].text_input("Nombre", parsed.get("nombre", ""), key="nombre")
    dni = row1[1].text_input("DNI", parsed.get("dni", ""), key="dni")
    telefono = row1[2].text_input("Teléfono", parsed.get("telefono", ""), key="telefono")
    direccion = row1[3].text_input("Dirección", parsed.get("direccion", ""), key="direccion")
    email = row1[4].text_input("Email", parsed.get("email", ""), key="email")
    
    st.markdown("**Acompañante**")
    acomp = parsed.get("acompanantes", [])
    row2 = st.columns(5)
    nombre_acomp = row2[0].text_input("Nombre", acomp[0]["nombre"] if acomp else "", key="nombre_acomp")
    dni_acomp = row2[1].text_input("DNI", acomp[0]["dni"] if acomp else "", key="dni_acomp")

# BLOQUE 2: RESERVA
with st.expander("🛎️ Información de Reserva", expanded=True):
    row_res = st.columns(6)
    checkin = row_res[0].text_input("Check-in", parsed.get("check_in", ""), key="checkin")
    checkout = row_res[1].text_input("Check-out", parsed.get("check_out", ""), key="checkout")
    noches = row_res[2].text_input("Noches", parsed.get("noches", ""), key="noches")
    personas = row_res[3].text_input("Personas", parsed.get("personas", ""), key="personas")
    habitacion = row_res[4].text_input("Habitación", parsed.get("habitacion", ""), key="habitacion")
    pension = row_res[5].text_input("Pensión", parsed.get("pension", ""), key="pension")

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

# --- Nuevo: actualizar montos en session_state si cambiaron ---
# La condición original (`st.session_state.last_raw == raw`) hacía que los montos no se
# actualizaran en el mismo re-run que cuando se pegaba texto nuevo.
# Lo cambiamos para que se actualicen siempre, asegurando consistencia.
if "last_raw" in st.session_state:
	st.session_state["total"] = total_str
	st.session_state["senal"] = senal_str
	st.session_state["saldo"] = saldo_str

# BLOQUE 3: MONTOS
with st.expander("💲 Montos", expanded=True):
    row_montos = st.columns(3)
    total = row_montos[0].text_input("Total", total_str, key="total")
    senal = row_montos[1].text_input("Seña", senal_str, key="senal")
    saldo = row_montos[2].text_input("Saldo", saldo_str, key="saldo")

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

# Insertar inmediatamente después del bloque st.markdown(...) existente que inyecta CSS
st.markdown("""
<style>
/* Botones modernos - opción: degradé verde de la marca */
div.stButton > button,
div.stDownloadButton > button,
.stButton>button, /* por compatibilidad */
.stDownloadButton>button {
  background: linear-gradient(90deg, #007f3f 0%, #5fbf00 100%);
  color: #ffffff !important;
  border: none !important;
  padding: 0.6rem 1.1rem !important;
  border-radius: 12px !important;
  font-weight: 700 !important;
  letter-spacing: 0.2px;
  box-shadow: 0 8px 22px rgba(95,191,0,0.16);
  transition: transform .14s ease, box-shadow .14s ease, opacity .14s ease;
  cursor: pointer;
  outline: none !important;
}

/* Hover / foco */
div.stButton > button:hover,
div.stDownloadButton > button:hover,
.stButton>button:hover,
.stDownloadButton>button:hover {
  transform: translateY(-3px);
  box-shadow: 0 14px 34px rgba(95,191,0,0.22);
  opacity: 0.98;
}

/* Presionado */
div.stButton > button:active,
div.stDownloadButton > button:active {
  transform: translateY(0);
  box-shadow: 0 6px 14px rgba(0,0,0,0.12);
}

/* Disabled */
div.stButton > button[disabled],
div.stDownloadButton > button[disabled] {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
}

/* Pequeño ajuste para iconos dentro del botón (si los tiene) */
div.stButton > button svg,
div.stDownloadButton > button svg {
  filter: brightness(0) invert(1);
  margin-right: 8px;
}

/* Alternativa (comentada): degradé violeta-azul
.div.stButtonAlt > button {
  background: linear-gradient(90deg, #6a00f4 0%, #00c0ff 100%);
}
*/
</style>
""", unsafe_allow_html=True)
