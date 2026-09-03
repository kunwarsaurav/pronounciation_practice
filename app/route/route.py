from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from typing import Optional
import logging
from app.scorer.individual import score_individual
from app.scorer.sentence import score_sentence

logger = logging.getLogger(__name__)

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
    logger.info(f"Received /score/individual request for word: '{target_word}'")
    
    if not audio.filename:
        logger.warning("No audio file uploaded for individual scoring.")
        raise HTTPException(status_code=400, detail="No audio file uploaded.")
    
    try:
        # Read file contents
        audio_bytes = await audio.read()
        
        # Call the scorer
        result = score_individual(target_word, audio_bytes, audio.filename)
        
        logger.info(f"Successfully scored individual word '{target_word}' with score {result.get('score', 0)}")
        return result
    except Exception as e:
        logger.error(f"Error processing individual scoring for '{target_word}': {e}", exc_info=True)
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
    logger.info(f"Received /score/sentence request for target word: '{target_word}'")
    
    if not audio.filename:
        logger.warning("No audio file uploaded for sentence scoring.")
        raise HTTPException(status_code=400, detail="No audio file uploaded.")
        
    try:
        # Read file contents
        audio_bytes = await audio.read()
        
        # Call the scorer
        result = score_sentence(target_word, audio_bytes, audio.filename)
        
        logger.info(f"Successfully scored sentence targeting '{target_word}' with final score {result.get('score', 0)}")
        return result
    except Exception as e:
        logger.error(f"Error processing sentence scoring for '{target_word}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
