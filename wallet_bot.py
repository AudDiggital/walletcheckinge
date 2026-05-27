"""
Bot de Telegram - Consulta de Wallets USDT
==========================================
Dependencias:
    pip install python-telegram-bot gspread google-auth pytz

Columnas del Google Sheet (pestaña: bottelegram):
    A: Wallet A
    B: Wallet B
    C: Etiqueta
    D: Monto
    E: Tipo       (Enviado / Recibido)
    F: Fecha
    G: Enlace
"""

import logging
from datetime import datetime

import gspread
import pytz
from google.oauth2.service_account import Credentials
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ─────────────────────────────────────────────
#  CONFIGURACIÓN — edita estos valores
# ─────────────────────────────────────────────

TELEGRAM_TOKEN = "8789308130:AAHM3F7mBStV6IXSGd3ktmBSp6nN9AyCDdQ"
GOOGLE_CREDENTIALS_FILE = "credentials.json"
SPREADSHEET_NAME = "Tronscan Wallet Lore"
SHEET_NAME = "bottelegram"

# IDs de Telegram autorizados (deja vacío [] para permitir a todos)
ALLOWED_USERS = []

# Zona horaria
TIMEZONE = "America/Bogota"

# Índices de columnas (0 = columna A)
COL_WALLET_A = 0   # A
COL_WALLET_B = 1   # B
COL_ETIQUETA = 2   # C
COL_MONTO    = 3   # D
COL_TIPO     = 4   # E
COL_FECHA    = 5   # F
COL_ENLACE   = 6   # G

# ─────────────────────────────────────────────
#  LOGS
# ─────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s │ %(levelname)s │ %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  GOOGLE SHEETS
# ─────────────────────────────────────────────

def get_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open(SPREADSHEET_NAME).worksheet(SHEET_NAME)


def safe_col(row, idx):
    """Retorna el valor de la columna o '—' si no existe."""
    return row[idx].strip() if len(row) > idx and row[idx].strip() else "—"


def buscar_wallet(wallet_input: str):
    """
    Busca en columnas A (Wallet A) y B (Wallet B).
    Retorna lista de todos los registros coincidentes.
    """
    try:
        sheet = get_sheet()
        rows = sheet.get_all_values()
        wallet_clean = wallet_input.strip().lower()
        resultados = []

        for row in rows[1:]:  # Salta encabezados
            if len(row) < 1:
                continue
            wallet_a = row[COL_WALLET_A].strip().lower() if len(row) > COL_WALLET_A else ""
            wallet_b = row[COL_WALLET_B].strip().lower() if len(row) > COL_WALLET_B else ""

            if wallet_clean in (wallet_a, wallet_b):
                resultados.append({
                    "wallet_a":  safe_col(row, COL_WALLET_A),
                    "wallet_b":  safe_col(row, COL_WALLET_B),
                    "etiqueta":  safe_col(row, COL_ETIQUETA),
                    "monto":     safe_col(row, COL_MONTO),
                    "tipo":      safe_col(row, COL_TIPO),
                    "fecha":     safe_col(row, COL_FECHA),
                    "enlace":    safe_col(row, COL_ENLACE),
                })

        return resultados

    except gspread.exceptions.SpreadsheetNotFound:
        logger.error("No se encontró el spreadsheet '%s'", SPREADSHEET_NAME)
        raise
    except Exception as e:
        logger.error("Error consultando Sheets: %s", e)
        raise


def hora_reporte() -> str:
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz).strftime("%d/%m/%Y · %H:%M %Z")


def emoji_tipo(tipo: str) -> str:
    """🔴 flecha si es Enviado, 🟢 si es Recibido."""
    t = tipo.strip().lower()
    if t == "enviado":
        return "🔴➡️  *Enviado*"
    elif t == "recibido":
        return "🟢⬅️  *Recibido*"
    else:
        return f"↔️  {tipo}"


def formatear_bloque(d: dict, numero: int = None) -> str:
    """Formatea un registro individual."""
    prefijo = f"▪️ *Registro {numero}*\n" if numero else ""
    indent  = "   " if numero else ""

    # Enlace clicable si existe
    enlace_str = f"[Ver enlace]({d['enlace']})" if d["enlace"] != "—" else "—"

    return (
        f"{prefijo}"
        f"{indent}💼  *Wallet A:*  `{d['wallet_a']}`\n"
        f"{indent}💼  *Wallet B:*  `{d['wallet_b']}`\n"
        f"{indent}🏷️  *Etiqueta:*  {d['etiqueta']}\n"
        f"{indent}💰  *Monto:*  `{d['monto']} USDT`\n"
        f"{indent}📤  *Tipo:*  {emoji_tipo(d['tipo'])}\n"
        f"{indent}📅  *Fecha:*  {d['fecha']}\n"
        f"{indent}🔗  *Enlace:*  {enlace_str}"
    )


def formatear_respuesta_encontrada(resultados: list, wallet_consultada: str) -> str:
    total = len(resultados)
    encabezado = (
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋  *RESULTADO DE CONSULTA*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔍  *Wallet consultada:*\n`{wallet_consultada}`\n\n"
        "🔴  *Riesgo:*  `ALTO`  ⚠️\n"
        "_(Wallet registrada en base de datos)_\n\n"
    )

    if total == 1:
        cuerpo = formatear_bloque(resultados[0])
    else:
        encabezado += f"📌  *{total} registros encontrados:*\n\n"
        cuerpo = "\n\n".join(
            formatear_bloque(d, i) for i, d in enumerate(resultados, start=1)
        )

    pie = f"\n\n🕐  *Hora de reporte:*  {hora_reporte()}\n\n━━━━━━━━━━━━━━━━━━━━━━━━"
    return encabezado + cuerpo + pie


def formatear_respuesta_no_encontrada(wallet: str) -> str:
    return (
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋  *RESULTADO DE CONSULTA*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔍  *Wallet consultada:*\n`{wallet}`\n\n"
        "🟢  *Riesgo:*  `BAJO`  ✅\n"
        "_(Wallet no registrada en base de datos)_\n\n"
        "💼  *Wallet A:*  —\n"
        "💼  *Wallet B:*  —\n"
        "🏷️  *Etiqueta:*  —\n"
        "💰  *Monto:*  —\n"
        "📤  *Tipo:*  —\n"
        "📅  *Fecha:*  —\n"
        "🔗  *Enlace:*  —\n\n"
        f"🕐  *Hora de reporte:*  {hora_reporte()}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━"
    )


# ─────────────────────────────────────────────
#  CONTROL DE ACCESO
# ─────────────────────────────────────────────

def usuario_autorizado(user_id: int) -> bool:
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS


# ─────────────────────────────────────────────
#  HANDLERS
# ─────────────────────────────────────────────

async def comando_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not usuario_autorizado(user.id):
        await update.message.reply_text("⛔ No tienes permiso para usar este bot.")
        return
    await update.message.reply_text(
        f"👋 Hola, *{user.first_name}*\!\n\n"
        "Envíame una *dirección de wallet USDT* y te consultaré "
        "la información en la base de datos\.\n\n"
        "📌 *Ejemplo:*\n`TXyz1234abcd5678efgh9012ijkl3456mn`\n\n"
        "También puedes usar:\n"
        "🔍 `/consultar <wallet>` — consulta directa\n"
        "ℹ️ `/ayuda` — ver instrucciones",
        parse_mode="MarkdownV2",
    )


async def comando_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not usuario_autorizado(update.effective_user.id):
        return
    await update.message.reply_text(
        "ℹ️ *Cómo usar este bot*\n\n"
        "Envía la dirección de wallet directamente al chat\.\n\n"
        "*Comandos:*\n"
        "▪️ `/start` — iniciar\n"
        "▪️ `/consultar <wallet>` — consulta directa\n"
        "▪️ `/ayuda` — esta ayuda\n\n"
        "*Resultado:*\n"
        "🔴 Riesgo *ALTO* → Wallet en base de datos \(col\. A o B\)\n"
        "🟢 Riesgo *BAJO* → Wallet no registrada\n\n"
        "*Tipo de transacción:*\n"
        "🔴➡️ Enviado\n"
        "🟢⬅️ Recibido",
        parse_mode="MarkdownV2",
    )


async def comando_consultar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not usuario_autorizado(update.effective_user.id):
        await update.message.reply_text("⛔ No tienes permiso para usar este bot.")
        return
    if not context.args:
        await update.message.reply_text(
            "⚠️ Uso: `/consultar <dirección_wallet>`",
            parse_mode="MarkdownV2",
        )
        return
    await procesar_wallet(update, context.args[0].strip())


async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not usuario_autorizado(update.effective_user.id):
        await update.message.reply_text("⛔ No tienes permiso para usar este bot.")
        return
    texto = update.message.text.strip()
    if len(texto) < 10 or texto.startswith("/"):
        await update.message.reply_text(
            "⚠️ Envía una dirección de wallet válida\\.\n"
            "Ejemplo: `TXyz1234abcd5678efgh9012ijkl3456mn`",
            parse_mode="MarkdownV2",
        )
        return
    await procesar_wallet(update, texto)


async def enviar_mensaje_largo(update: Update, texto: str) -> None:
    """Divide mensajes que superan el límite de 4096 caracteres de Telegram."""
    LIMITE = 4000
    if len(texto) <= LIMITE:
        await update.message.reply_text(texto, parse_mode="Markdown")
        return

    # Divide por bloques de registros (separados por línea vacía doble)
    partes = []
    actual = ""
    for linea in texto.split("\n"):
        if len(actual) + len(linea) + 1 > LIMITE:
            partes.append(actual.strip())
            actual = linea + "\n"
        else:
            actual += linea + "\n"
    if actual.strip():
        partes.append(actual.strip())

    total = len(partes)
    for i, parte in enumerate(partes, start=1):
        sufijo = f"\n\n_Mensaje {i}/{total}_" if total > 1 else ""
        await update.message.reply_text(parte + sufijo, parse_mode="Markdown")


async def procesar_wallet(update: Update, wallet: str) -> None:
    await update.message.chat.send_action("typing")
    logger.info("Consulta wallet '%s' por usuario %s", wallet, update.effective_user.id)

    try:
        resultados = buscar_wallet(wallet)
        if resultados:
            respuesta = formatear_respuesta_encontrada(resultados, wallet)
        else:
            respuesta = formatear_respuesta_no_encontrada(wallet)
        await enviar_mensaje_largo(update, respuesta)

    except gspread.exceptions.SpreadsheetNotFound:
        await update.message.reply_text(
            "❌ Error: No se encontró la hoja de cálculo\\.\n"
            "Verifica el nombre en la configuración del bot\\.",
            parse_mode="MarkdownV2",
        )
    except Exception as e:
        logger.error("Error inesperado: %s", e)
        await update.message.reply_text(
            "❌ Ocurrió un error al consultar la base de datos\\. "
            "Intenta de nuevo en unos segundos\\.",
            parse_mode="MarkdownV2",
        )


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main() -> None:
    logger.info("Iniciando bot de wallets USDT...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",     comando_start))
    app.add_handler(CommandHandler("ayuda",     comando_ayuda))
    app.add_handler(CommandHandler("consultar", comando_consultar))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje))
    logger.info("Bot corriendo. Presiona Ctrl+C para detener.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
