import os
import uuid
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class VoiceRequest(BaseModel):
    text: str
    voice: str = "en-US-JennyNeural"
    rate: str = "+0%"
    pitch: str = "+0Hz"
    volume: str = "+0%"


@router.get("/voices")
async def list_voices():
    try:
        import edge_tts
        voices = await edge_tts.list_voices()
        result = [
            {
                "name": v["Name"],
                "display": v["ShortName"],
                "locale": v["Locale"],
                "gender": v["Gender"],
            }
            for v in voices
            if v["Locale"].startswith("en")
        ]
        all_voices = await edge_tts.list_voices()
        all_result = [
            {
                "name": v["Name"],
                "display": v["ShortName"],
                "locale": v["Locale"],
                "gender": v["Gender"],
            }
            for v in all_voices
        ]
        return {"voices": all_result}
    except Exception as e:
        return {"voices": [], "error": str(e)}


@router.post("/generate")
async def generate_voice(req: VoiceRequest):
    try:
        import edge_tts

        output_dir = "outputs/voice"
        filename = f"{uuid.uuid4()}.mp3"
        filepath = os.path.join(output_dir, filename)

        communicate = edge_tts.Communicate(
            text=req.text,
            voice=req.voice,
            rate=req.rate,
            pitch=req.pitch,
            volume=req.volume,
        )
        await communicate.save(filepath)

        return {
            "status": "completed",
            "result": f"/outputs/voice/{filename}",
            "filename": filename,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
