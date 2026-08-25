from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from typing import Optional
from app.scorer.individual import score_individual
from app.scorer.sentence import score_sentence

router = APIRouter(prefix="/score", tags=["Scoring"])

@router.post("/individual")
async def score_individual_endpoint(
    target_word: str = Form(...),
    audio: UploadFile = File(...)
):
    """
    Endpoint for Individual Word Pronunciation Scoring.
    Expects the target vocabulary word and the student's audio recording.
    """
    if not audio.filename:
        raise HTTPException(status_code=400, detail="No audio file uploaded.")
    
    try:
        # Read file contents
        audio_bytes = await audio.read()
        
        # Call the scorer
        result = score_individual(target_word, audio_bytes)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sentence")
async def score_sentence_endpoint(
    target_word: str = Form(...),
    audio: UploadFile = File(...)
):
    """
    Endpoint for Sentence Pronunciation Scoring.
    Expects the target vocabulary word and the student's audio recording.
    """
    if not audio.filename:
        raise HTTPException(status_code=400, detail="No audio file uploaded.")
        
    try:
        # Read file contents
        audio_bytes = await audio.read()
        
        # Call the scorer
        result = score_sentence(target_word, audio_bytes)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
