"""
Bot de Telegram - Consulta de Wallets USDT
==========================================
Dependencias:
    pip install python-telegram-bot gspread google-auth pytz

Configuración necesaria:
    1. Crear bot con @BotFather en Telegram → obtener TOKEN
    2. Activar Google Sheets API en Google Cloud Console
    3. Crear cuenta de servicio y descargar credentials.json
    4. Compartir tu Google Sheet con el email de la cuenta de servicio
    5. Llenar las variables de la sección CONFIGURACIÓN abajo
"""

import logging
import re
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

TELEGRAM_TOKEN = "8789308130:AAHM3F7mBStV6IXSGd3ktmBSp6nN9AyCDdQ"          # Token de @BotFather
GOOGLE_CREDENTIALS_FILE = "credentials.json"  # Archivo descargado de Google Cloud
SPREADSHEET_NAME = "Tronscan Wallet Lore"    # Nombre exacto del archivo en Drive
SHEET_NAME = "Bottelegram"                         # Nombre de la pestaña (tab)

# IDs de Telegram autorizados (deja vacío [] para permitir a todos)
# Ejemplo: ALLOWED_USERS = [123456789, 987654321]
ALLOWED_USERS = []

# Zona horaria para la hora del reporte
TIMEZONE = "America/Bogota"

# Columnas de tu Google Sheet (índice 0 = columna A)
COL_WALLET  = 0   # Columna A
COL_LABEL   = 1   # Columna B
COL_BALANCE = 2   # Columna C

# ─────────────────────────────────────────────
#  CONFIGURACIÓN DE LOGS
# ─────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s │ %(levelname)s │ %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  CONEXIÓN A GOOGLE SHEETS
# ─────────────────────────────────────────────

def get_sheet():
    """Retorna la hoja de Google Sheets configurada."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    spreadsheet = client.open(SPREADSHEET_NAME)
    return spreadsheet.worksheet(SHEET_NAME)


def buscar_wallet(wallet_input: str):
    """
    Busca la wallet en Google Sheets (insensible a mayúsculas/espacios).
    Retorna una LISTA con todos los registros encontrados, o lista vacía si no existe.
    Soporta múltiples filas con la misma wallet.
    """
    try:
        sheet = get_sheet()
        rows = sheet.get_all_values()

        wallet_input_clean = wallet_input.strip().lower()
        resultados = []

        for row in rows[1:]:  # Salta la fila de encabezados
            if len(row) < 1:
                continue
            wallet_sheet = row[COL_WALLET].strip().lower()
            if wallet_sheet == wallet_input_clean:
                resultados.append({
                    "wallet":  row[COL_WALLET].strip(),
                    "label":   row[COL_LABEL].strip()   if len(row) > COL_LABEL   else "—",
                    "balance": row[COL_BALANCE].strip() if len(row) > COL_BALANCE else "—",
                })

        return resultados  # Lista vacía = no encontrada

    except gspread.exceptions.SpreadsheetNotFound:
        logger.error("No se encontró el spreadsheet '%s'", SPREADSHEET_NAME)
        raise
    except Exception as e:
        logger.error("Error consultando Sheets: %s", e)
        raise


def hora_reporte() -> str:
    """Retorna la hora actual formateada en la zona horaria configurada."""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    return now.strftime("%d/%m/%Y · %H:%M %Z")


def formatear_respuesta_encontrada(resultados: list) -> str:
    """
    Formatea el mensaje cuando la wallet SÍ está en la base de datos.
    Si hay múltiples registros, muestra cada uno numerado.
    """
    wallet = resultados[0]["wallet"]
    total = len(resultados)

    if total == 1:
        # Un solo registro — formato simple
        d = resultados[0]
        return (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📋  *RESULTADO DE CONSULTA*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💼  *Wallet:*\n`{d['wallet']}`\n\n"
            f"🏷️  *Etiqueta:*  {d['label']}\n\n"
            "🔴  *Riesgo:*  `ALTO`  ⚠️\n"
            "_(Wallet registrada en base de datos)_\n\n"
            f"💰  *Saldo:*  `{d['balance']} USDT`\n\n"
            f"🕐  *Hora de reporte:*  {hora_reporte()}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━"
        )
    else:
        # Múltiples registros — muestra cada uno numerado
        encabezado = (
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📋  *RESULTADO DE CONSULTA*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💼  *Wallet:*\n`{wallet}`\n\n"
            "🔴  *Riesgo:*  `ALTO`  ⚠️\n"
            "_(Wallet registrada en base de datos)_\n\n"
            f"📌  *{total} registros encontrados:*\n\n"
        )
        bloques = []
        for i, d in enumerate(resultados, start=1):
            bloque = (
                f"▪️ *Registro {i}*\n"
                f"   🏷️  Etiqueta:  {d['label']}\n"
                f"   💰  Saldo:  `{d['balance']} USDT`"
            )
            bloques.append(bloque)

        pie = (
            f"\n\n🕐  *Hora de reporte:*  {hora_reporte()}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        return encabezado + "\n\n".join(bloques) + pie


def formatear_respuesta_no_encontrada(wallet: str) -> str:
    """Formatea el mensaje cuando la wallet NO está en la base de datos."""
    return (
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋  *RESULTADO DE CONSULTA*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💼  *Wallet:*\n`{wallet}`\n\n"
        "🏷️  *Etiqueta:*  —\n\n"
        "🟢  *Riesgo:*  `BAJO`  ✅\n"
        "_(Wallet no registrada en base de datos)_\n\n"
        "💰  *Saldo:*  —\n\n"
        f"🕐  *Hora de reporte:*  {hora_reporte()}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━"
    )


# ─────────────────────────────────────────────
#  MIDDLEWARE: CONTROL DE ACCESO
# ─────────────────────────────────────────────

def usuario_autorizado(user_id: int) -> bool:
    """Retorna True si el usuario tiene acceso (o si no hay lista de restricción)."""
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS


# ─────────────────────────────────────────────
#  HANDLERS DEL BOT
# ─────────────────────────────────────────────

async def comando_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde al comando /start con instrucciones."""
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
    """Muestra la ayuda del bot."""
    if not usuario_autorizado(update.effective_user.id):
        return

    await update.message.reply_text(
        "ℹ️ *Cómo usar este bot*\n\n"
        "Simplemente envía la dirección de la wallet en el chat\.\n\n"
        "*Comandos disponibles:*\n"
        "▪️ `/start` — iniciar el bot\n"
        "▪️ `/consultar <wallet>` — consulta directa\n"
        "▪️ `/ayuda` — esta ayuda\n\n"
        "*Interpretación del resultado:*\n"
        "🔴 Riesgo *ALTO* → Wallet en base de datos\n"
        "🟢 Riesgo *BAJO* → Wallet no registrada",
        parse_mode="MarkdownV2",
    )


async def comando_consultar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Permite consultar con /consultar <wallet>."""
    if not usuario_autorizado(update.effective_user.id):
        await update.message.reply_text("⛔ No tienes permiso para usar este bot.")
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ Uso: `/consultar <dirección_wallet>`",
            parse_mode="MarkdownV2",
        )
        return

    wallet = context.args[0].strip()
    await procesar_wallet(update, wallet)


async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Intercepta cualquier mensaje de texto y lo trata como una wallet."""
    if not usuario_autorizado(update.effective_user.id):
        await update.message.reply_text("⛔ No tienes permiso para usar este bot.")
        return

    texto = update.message.text.strip()

    # Ignora mensajes muy cortos o que sean comandos
    if len(texto) < 10 or texto.startswith("/"):
        await update.message.reply_text(
            "⚠️ Envía una dirección de wallet válida\\.\n"
            "Ejemplo: `TXyz1234abcd5678efgh9012ijkl3456mn`",
            parse_mode="MarkdownV2",
        )
        return

    await procesar_wallet(update, texto)


async def procesar_wallet(update: Update, wallet: str) -> None:
    """Lógica central: busca la wallet y responde con el formato correcto."""
    # Indicador de "escribiendo..."
    await update.message.chat.send_action("typing")

    logger.info(
        "Consulta de wallet '%s' por usuario %s",
        wallet,
        update.effective_user.id,
    )

    try:
        resultados = buscar_wallet(wallet)

        if resultados:
            respuesta = formatear_respuesta_encontrada(resultados)
        else:
            respuesta = formatear_respuesta_no_encontrada(wallet)

        await update.message.reply_text(respuesta, parse_mode="Markdown")

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
#  INICIO DEL BOT
# ─────────────────────────────────────────────

def main() -> None:
    """Arranca el bot."""
    logger.info("Iniciando bot de wallets USDT...")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Registrar handlers
    app.add_handler(CommandHandler("start",     comando_start))
    app.add_handler(CommandHandler("ayuda",     comando_ayuda))
    app.add_handler(CommandHandler("consultar", comando_consultar))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje))

    logger.info("Bot corriendo. Presiona Ctrl+C para detener.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
