
import asyncio
import re
import subprocess
import tempfile
from pathlib import Path
from fastapi.responses import FileResponse, Response
from app.services.tts_service import synthesize_audio

import httpx

from fastapi import (
    APIRouter,
    HTTPException,
    UploadFile,
    File,
)
from fastapi.responses import FileResponse, Response

from app.api.schemas import (
    SessionStart,
    ConversationRequest,
    CartRequest,
    CustomerRequest,
)
from app.config import RECEIPTS_DIR
from app.services.session_service import (
    create_session,
    get_session,
    save_session,
)
from app.services.cart_service import (
    cart_details,
    add_items,
    remove_items,
)
from app.services.ai_waiter import ask_waiter
from app.services.checkout_service import create_receipt
from app.services.speech_service import transcribe_audio


router = APIRouter(prefix="/api")

MENU_DATA = None
MENU = []
MENU_BY_ID = {}
RESTAURANT = "Namma Veedu"

MAX_AUDIO_SIZE = 15 * 1024 * 1024
PIPER_URL = "http://127.0.0.1:5000/synthesize"


def configure(menu_data):
    global MENU_DATA, MENU, MENU_BY_ID, RESTAURANT

    MENU_DATA = menu_data
    MENU = menu_data["items"]
    MENU_BY_ID = {x["id"]: x for x in MENU}
    RESTAURANT = menu_data.get("restaurant_name", RESTAURANT)


def response(session, action, message, **extra):
    return {
        "success": True,
        "action": action,
        "message": message,
        "cart": cart_details(session["cart"], MENU_BY_ID),
        "checkout_pending": session["checkout_pending"],
        **extra,
    }


# --------------------------------------------------
# SESSION
# --------------------------------------------------

@router.post("/session")
def start_session(data: SessionStart):
    sid = create_session()
    session = get_session(sid)

    if data.customer_name:
        session["customer_name"] = data.customer_name.strip()

    save_session(session)

    return {
        "success": True,
        "session_id": sid,
        "customer_name": session["customer_name"],
        "cart": cart_details(session["cart"], MENU_BY_ID),
    }


@router.post("/customer")
def set_customer(data: CustomerRequest):
    session = get_session(data.session_id)

    session["customer_name"] = data.name.strip()
    session["customer_phone"] = (
        data.phone.strip() if data.phone else None
    )

    save_session(session)

    return {
        "success": True,
        "name": session["customer_name"],
        "reply": (
            f"Hello {session['customer_name']}! "
            f"Welcome to {RESTAURANT}. "
            "What would you like to order today?"
        ),
    }


# --------------------------------------------------
# MENU
# --------------------------------------------------

@router.get("/menu")
def get_menu():
    return {
        "restaurant": RESTAURANT,
        "items": MENU,
    }


# --------------------------------------------------
# SPEECH: AUDIO TO TEXT
# --------------------------------------------------

@router.post("/speech/transcribe")
async def speech_transcribe(audio: UploadFile = File(...)):
    """
    Receive browser audio, convert it to mono 16 kHz WAV,
    and transcribe it using local Sherpa-ONNX.
    """

    data = await audio.read(MAX_AUDIO_SIZE + 1)

    if not data:
        raise HTTPException(400, "No audio was received.")

    if len(data) > MAX_AUDIO_SIZE:
        raise HTTPException(413, "Audio recording is too large.")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "recording.input"
            output_path = Path(temp_dir) / "recording.wav"

            input_path.write_bytes(data)

            def convert_audio():
                subprocess.run(
                    [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel", "error",
                        "-y",
                        "-i", str(input_path),
                        "-vn",
                        "-ac", "1",
                        "-ar", "16000",
                        "-c:a", "pcm_s16le",
                        str(output_path),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=30,
                )

            await asyncio.to_thread(convert_audio)

            transcript = await asyncio.to_thread(
                transcribe_audio,
                str(output_path),
            )

            return {
                "success": True,
                "text": transcript,
            }

    except subprocess.CalledProcessError as exc:
        raise HTTPException(
            400,
            "Could not decode the audio recording. "
            "Please try speaking again.",
        ) from exc

    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            408,
            "Audio conversion timed out.",
        ) from exc

    except FileNotFoundError as exc:
        raise HTTPException(
            500,
            f"Required speech file or FFmpeg was not found: {exc}",
        ) from exc

    except Exception as exc:
        raise HTTPException(
            500,
            f"Speech recognition failed: {exc}",
        ) from exc

    finally:
        await audio.close()


# --------------------------------------------------
# SPEECH: TEXT TO AUDIO
# --------------------------------------------------

@router.post("/speech/synthesize")
async def speech_synthesize(payload: dict):
    """Generate speech using the local Piper HTTP server."""

    text = str(payload.get("text", "")).strip()

    if not text:
        raise HTTPException(400, "Text is required.")

    if len(text) > 1000:
        raise HTTPException(400, "Text is too long.")

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            result = await client.post(
                PIPER_URL,
                json={
                    "text": text,
                    "length_scale": 0.90,
                },
            )

            result.raise_for_status()

            return Response(
                content=result.content,
                media_type="audio/wav",
            )

    except httpx.HTTPError as exc:
        raise HTTPException(
            503,
            "The local Piper speech service is unavailable.",
        ) from exc


# --------------------------------------------------
# CART
# --------------------------------------------------

@router.get("/cart/{session_id}")
def get_cart(session_id: str):
    session = get_session(session_id)

    return {
        "success": True,
        "cart": cart_details(session["cart"], MENU_BY_ID),
        "checkout_pending": session["checkout_pending"],
    }


@router.post("/cart/add")
def add_cart(data: CartRequest):
    session = get_session(data.session_id)

    if session["checkout_pending"] or session["status"] != "active":
        raise HTTPException(
            409,
            "This order cannot be changed right now.",
        )

    add_items(
        session["cart"],
        [{"id": data.item_id, "quantity": data.quantity}],
        MENU_BY_ID,
    )

    save_session(session)

    return {
        "success": True,
        "cart": cart_details(session["cart"], MENU_BY_ID),
    }


@router.post("/cart/remove")
def remove_cart(data: CartRequest):
    session = get_session(data.session_id)

    if session["checkout_pending"] or session["status"] != "active":
        raise HTTPException(
            409,
            "This order cannot be changed right now.",
        )

    if data.item_id not in MENU_BY_ID:
        raise HTTPException(400, "Invalid menu item.")

    remove_items(
        session["cart"],
        [{"id": data.item_id, "quantity": data.quantity}],
    )

    save_session(session)

    return {
        "success": True,
        "cart": cart_details(session["cart"], MENU_BY_ID),
    }


# --------------------------------------------------
# CONVERSATION AND CHECKOUT
# --------------------------------------------------

YES = {
    "yes", "yes please", "yeah", "yeah please",
    "yep", "yep please", "yup", "sure", "sure please",
    "okay", "okay please", "ok", "ok please",
    "correct", "absolutely", "please do", "go ahead",
    "confirm", "confirm order", "confirm my order",
}

NO = {
    "no", "no thanks", "no thank you", "nope",
    "nah", "not now", "cancel", "wait",
    "do not", "dont",
}


def normalize(text):
    return re.sub(
        r"[^a-z0-9 ]+",
        " ",
        text.lower().replace("'", ""),
    ).strip()


def checkout_decision(text):
    normalized = " ".join(normalize(text).split())

    if normalized in YES:
        return "yes"

    if normalized in NO:
        return "no"

    return None


def is_done(text):
    normalized = " ".join(normalize(text).split())

    return normalized in {
        "thats all",
        "that is all",
        "thats it",
        "that is it",
        "im done",
        "i am done",
        "nothing else",
        "no more items",
        "checkout",
        "check out",
        "finish my order",
        "complete my order",
        "place my order",
    }


@router.post("/conversation")
def conversation(data: ConversationRequest):
    session = get_session(data.session_id)
    text = data.text.strip()

    if session["status"] != "active":
        return response(
            session,
            "answer",
            "This order has already been confirmed. "
            "Please start a new session.",
        )

    if session["checkout_pending"]:
        decision = checkout_decision(text)

        if decision == "yes":
            try:
                receipt = create_receipt(
                    session,
                    MENU_BY_ID,
                    RESTAURANT,
                )
            except ValueError as exc:
                raise HTTPException(400, str(exc))

            session["checkout_pending"] = False
            session["status"] = "confirmed"

            session["history"] += [
                {"role": "user", "content": text},
                {
                    "role": "assistant",
                    "content": "Your order is confirmed.",
                },
            ]

            save_session(session)

            return response(
                session,
                "confirm_checkout",
                (
                    f"Thank you! Your order is confirmed. "
                    f"Your total is Rs. {receipt['total']}. "
                    "Your receipt is ready."
                ),
                receipt=receipt,
            )

        if decision == "no":
            session["checkout_pending"] = False

            msg = (
                "Of course. We can continue ordering. "
                "What else would you like?"
            )

            session["history"] += [
                {"role": "user", "content": text},
                {"role": "assistant", "content": msg},
            ]

            save_session(session)

            return response(session, "cancel_checkout", msg)

        return response(
            session,
            "ask_checkout_confirmation",
            "Please say yes to confirm your order, "
            "or no to continue ordering.",
        )

    if is_done(text):
        if not session["cart"]:
            return response(
                session,
                "answer",
                "Your cart is empty. What would you like to order?",
            )

        session["checkout_pending"] = True

        msg = (
            "Your order is ready. Would you like me to "
            "confirm it and prepare your receipt?"
        )

        session["history"] += [
            {"role": "user", "content": text},
            {"role": "assistant", "content": msg},
        ]

        save_session(session)

        return response(
            session,
            "ask_checkout_confirmation",
            msg,
        )

    result = ask_waiter(
        text,
        MENU,
        [
            {"id": item_id, "quantity": quantity}
            for item_id, quantity in session["cart"].items()
        ],
        session["history"],
        False,
        RESTAURANT,
    )

    action = result["action"]

    if action == "confirm_checkout":
        action = "answer"
        result["message"] = (
            "I need your confirmation first. "
            "Would you like anything else?"
        )

    if action == "add_items":
        add_items(
            session["cart"],
            result["items_to_add"],
            MENU_BY_ID,
        )

    elif action == "remove_items":
        remove_items(
            session["cart"],
            result["items_to_remove"],
        )

    elif action == "ask_checkout_confirmation":
        if not session["cart"]:
            action = "answer"
            result["message"] = (
                "Your cart is empty. What would you like to order?"
            )
        else:
            session["checkout_pending"] = True

    session["history"] += [
        {"role": "user", "content": text},
        {
            "role": "assistant",
            "content": result["message"],
        },
    ]

    save_session(session)

    return response(
        session,
        action,
        result["message"],
    )


# --------------------------------------------------
# RECEIPT DOWNLOAD
# --------------------------------------------------

@router.get("/receipts/{receipt_id}")
def receipt_download(receipt_id: str):
    if not re.fullmatch(r"[a-f0-9]{16}", receipt_id):
        raise HTTPException(404, "Receipt not found.")

    path = RECEIPTS_DIR / f"receipt_{receipt_id}.pdf"

    if not path.is_file():
        raise HTTPException(404, "Receipt not found.")

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"restaurant_receipt_{receipt_id}.pdf",
    )



@router.post("/speech/synthesize")
def speech_synthesize(payload: dict):
    text = payload.get("text")

    if not isinstance(text, str) or not text.strip():
        raise HTTPException(400, "Text is required.")

    if len(text) > 1000:
        raise HTTPException(400, "Text is too long.")

    try:
        audio = synthesize_audio(text)

        return Response(
            content=audio,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "inline; filename=speech.wav"
            },
        )

    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    except FileNotFoundError as exc:
        raise HTTPException(
            500, "Piper voice model is unavailable."
        ) from exc
