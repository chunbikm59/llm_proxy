"""OpenAI 相容的 Whisper 音訊轉錄路由"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from routers.proxy import verify_key
from whisper_manager import WhisperCppManager

router = APIRouter(tags=["Audio"])


@router.post("/v1/audio/transcriptions")
async def audio_transcriptions(
    request: Request,
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    language: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
    response_format: str = Form("json"),
    temperature: float = Form(0.0),
    stream: bool = Form(False),
    cluster: Optional[str] = Form(None),
    key_info: dict = Depends(verify_key),
):
    """
    OpenAI 相容的音訊轉錄端點，委派給 WhisperCppManager 處理。

    stream=true 時回傳 NDJSON 串流，每行一個 segment：
        {"text": "[00:00:00.000 --> 00:00:03.500]  辨識文字"}
    stream=false（預設）時等全部完成後回傳完整結果。
    """
    mgr: WhisperCppManager = request.app.state.whisper_manager

    audio_bytes = await file.read()
    filename = file.filename or "audio"

    params = {
        "language": language,
        "prompt": prompt,
        "response_format": response_format,
        "temperature": temperature,
    }

    if stream:
        async def gen():
            agen = mgr.transcribe_stream(audio_bytes, filename, params, cluster_name=cluster)
            try:
                async for segment_line in agen:
                    yield json.dumps({"text": segment_line}, ensure_ascii=False) + "\n"
            except HTTPException as e:
                yield json.dumps({"error": e.detail}, ensure_ascii=False) + "\n"
            finally:
                await agen.aclose()

        return StreamingResponse(gen(), media_type="application/x-ndjson")

    # 非串流：等全部完成
    try:
        result = await mgr.transcribe(audio_bytes, filename, params, cluster_name=cluster)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if response_format in ("text", "srt", "vtt"):
        return PlainTextResponse(result.get("text", ""))

    return JSONResponse(content=result)
