import os
import io
import re
import torch
import torchaudio
from openai import OpenAI
from app.scorer.individual import score_individual

import imageio_ffmpeg
from pydub import AudioSegment
# Set pydub to use the ffmpeg binary from imageio-ffmpeg
AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()

def transcribe_audio_with_timestamps(audio_bytes: bytes, filename: str):
    """Uses Groq API via OpenAI client to transcribe audio with word-level timestamps."""
    api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("XAI_API_KEY")
    if not api_key:
        print("WARNING: GROQ_API_KEY not set. Skipping transcription.")
        return {"text": "", "words": []}
        
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )
    
    file_obj = io.BytesIO(audio_bytes)
    file_obj.name = filename
    
    try:
        response = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=file_obj,
            response_format="verbose_json",
            timestamp_granularities=["word"],
            language="en"
        )
        return {
            "text": response.text,
            "words": response.words if hasattr(response, 'words') else []
        }
    except Exception as e:
        print(f"Error calling xAI API with timestamps: {e}")
        return {"text": "", "words": []}

def extract_audio_segment(audio_bytes: bytes, start_time: float, end_time: float) -> bytes:
    """Extracts a segment of audio given start and end times in seconds."""
    file_obj = io.BytesIO(audio_bytes)
    audio = AudioSegment.from_file(file_obj)
    
    start_ms = int(start_time * 1000)
    end_ms = int(end_time * 1000)
    
    segment = audio[start_ms:end_ms]
    
    out_obj = io.BytesIO()
    segment.export(out_obj, format="wav")
    out_obj.seek(0)
    
    return out_obj.read()

def analyze_speech_rate(duration_seconds: float, words_count: int):
    """Basic speech rate analysis (words per minute)."""
    if duration_seconds == 0:
        return 0
    wpm = (words_count / duration_seconds) * 60
    return wpm

def score_sentence(target_word: str, audio_bytes: bytes, filename: str = "audio.wav"):
    # 1. Transcribe with timestamps
    transcription_data = transcribe_audio_with_timestamps(audio_bytes, filename)
    transcript = transcription_data.get("text", "")
    words = transcription_data.get("words", [])
    
    # 2. Check if target word was used
    target_clean = target_word.lower().strip()
    target_word_data = None
    
    for word_info in words:
        w_clean = re.sub(r'[^\w\s]', '', word_info.word.lower().strip())
        if w_clean == target_clean:
            target_word_data = word_info
            break
            
    target_word_detected = target_word_data is not None
    
    # 3. Process target word pronunciation if found
    target_word_score = 0
    feedback = []
    
    if target_word_detected:
        # Extract audio segment
        start_time = target_word_data.start
        end_time = target_word_data.end
        
        # Add a small padding (0.1s)
        start_time = max(0, start_time - 0.1)
        end_time = end_time + 0.1
        
        segment_bytes = extract_audio_segment(audio_bytes, start_time, end_time)
        
        # Score the individual word segment
        try:
            indiv_result = score_individual(target_word, segment_bytes)
            target_word_score = indiv_result.get("score", 0)
            
            if target_word_score >= 90:
                feedback.append(f"The target word '{target_word}' was pronounced clearly.")
            else:
                for f in indiv_result.get("feedback", []):
                    # Filter out the "we heard X but expected Y" feedback since we already localized it
                    if "We heard" not in f:
                        feedback.append(f"In '{target_word}': {f}")
        except Exception as e:
            print(f"Error scoring individual word segment: {e}")
            feedback.append(f"Could not analyze target word pronunciation in detail.")
    else:
        feedback.append(f"The required vocabulary word '{target_word}' was not detected in the sentence.")
        
    # 4. Analyze whole sentence delivery
    file_obj = io.BytesIO(audio_bytes)
    audio = AudioSegment.from_file(file_obj)
    
    wpm = analyze_speech_rate(audio.duration_seconds, len(words))
    
    if wpm < 90:
        feedback.append("Speech rate is quite slow. Try to speak a bit more naturally.")
    elif wpm > 160:
        feedback.append("Speech rate is very fast. Try slowing down slightly for clarity.")
        
    # 5. Final sentence score
    # MVP scoring logic:
    # 50% target word pronunciation, 50% basic delivery (presence of word and reasonable wpm)
    
    delivery_score = 100
    if not target_word_detected:
        delivery_score -= 50
    if wpm < 90 or wpm > 160:
        delivery_score -= 20
        
    final_score = int((target_word_score * 0.6) + (delivery_score * 0.4))
    if not target_word_detected:
        final_score = 0
        
    return {
        "score": final_score,
        "target_word": target_word,
        "target_word_detected": target_word_detected,
        "target_word_score": target_word_score,
        "transcript": transcript,
        "feedback": feedback,
        "metrics": {
            "words_per_minute": round(wpm, 1)
        }
    }
