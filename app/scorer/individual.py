import os
import io
import re
import numpy as np
import torch
import torchaudio
from openai import OpenAI
from g2p_en import G2p
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean
import librosa
from app.main import ml_models

# Initialize G2P
g2p = G2p()

# Basic mapping from ARPAbet to IPA for comparison with Wav2Vec2-Phoneme output
# (Note: This is a simplified mapping for MVP purposes)
ARPABET_TO_IPA = {
    'AA': 'ɑ', 'AE': 'æ', 'AH': 'ʌ', 'AO': 'ɔ', 'AW': 'aʊ', 'AY': 'aɪ',
    'B': 'b', 'CH': 'tʃ', 'D': 'd', 'DH': 'ð', 'EH': 'ɛ', 'ER': 'ɝ',
    'EY': 'eɪ', 'F': 'f', 'G': 'ɡ', 'HH': 'h', 'IH': 'ɪ', 'IY': 'i',
    'JH': 'dʒ', 'K': 'k', 'L': 'l', 'M': 'm', 'N': 'n', 'NG': 'ŋ',
    'OW': 'oʊ', 'OY': 'ɔɪ', 'P': 'p', 'R': 'ɹ', 'S': 's', 'SH': 'ʃ',
    'T': 't', 'TH': 'θ', 'UH': 'ʊ', 'UW': 'u', 'V': 'v', 'W': 'w',
    'Y': 'j', 'Z': 'z', 'ZH': 'ʒ'
}

def clean_arpabet(phoneme_list):
    """Remove stress markers from ARPAbet phonemes and convert to IPA."""
    ipa_list = []
    for p in phoneme_list:
        # Remove numbers (stress markers)
        clean_p = re.sub(r'\d+', '', p)
        if clean_p in ARPABET_TO_IPA:
            ipa_list.append(ARPABET_TO_IPA[clean_p])
    return ipa_list

def transcribe_audio_xai(audio_bytes: bytes, filename: str) -> str:
    """Uses Grok API (xAI) via OpenAI client to transcribe audio."""
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        print("WARNING: XAI_API_KEY not set. Skipping transcription.")
        return ""
        
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.x.ai/v1"
    )
    
    # We need to wrap the bytes in a file-like object with a name
    file_obj = io.BytesIO(audio_bytes)
    file_obj.name = filename
    
    try:
        response = client.audio.transcriptions.create(
            model="whisper-large-v3", # Grok API supported whisper model
            file=file_obj
        )
        return response.text
    except Exception as e:
        print(f"Error calling xAI API: {e}")
        return ""

import imageio_ffmpeg
from pydub import AudioSegment
# Set pydub to use the ffmpeg binary from imageio-ffmpeg
AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()

def preprocess_audio(audio_bytes: bytes, target_sr: int = 16000):
    """Load audio bytes using pydub (FFmpeg), convert to mono, and resample."""
    file_obj = io.BytesIO(audio_bytes)
    audio = AudioSegment.from_file(file_obj)
    
    # Convert to mono if stereo
    if audio.channels > 1:
        audio = audio.set_channels(1)
        
    # Resample
    if audio.frame_rate != target_sr:
        audio = audio.set_frame_rate(target_sr)
        
    # Get raw data as numpy array
    samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
    
    # Normalize to [-1.0, 1.0] (pydub uses PCM depending on sample_width)
    max_val = float(2**(audio.sample_width * 8 - 1))
    samples = samples / max_val
        
    return samples

def score_individual(target_word: str, audio_bytes: bytes, filename: str = "audio.wav"):
    # 1. Get canonical pronunciation
    arpabet_phonemes = g2p(target_word)
    # g2p_en returns punctuation as well, filter it out
    arpabet_phonemes = [p for p in arpabet_phonemes if p.isalnum()]
    expected_phonemes = clean_arpabet(arpabet_phonemes)
    
    if not expected_phonemes:
        raise ValueError(f"Could not determine canonical pronunciation for '{target_word}'")

    # 2. Run xAI STT
    transcript = transcribe_audio_xai(audio_bytes, filename)
    
    # 3. Verify target word
    recognized_word_clean = re.sub(r'[^\w\s]', '', transcript.lower().strip())
    target_clean = target_word.lower().strip()
    word_detected = target_clean in recognized_word_clean
    
    # 4. Run Wav2Vec2-Phoneme
    processor = ml_models.get("wav2vec2_processor")
    model = ml_models.get("wav2vec2_model")
    device = ml_models.get("device", "cpu")
    
    if not model or not processor:
        raise RuntimeError("ML Models not loaded. Is the server starting?")

    waveform = preprocess_audio(audio_bytes, target_sr=16000)
    
    inputs = processor(waveform, sampling_rate=16000, return_tensors="pt").to(device)
    
    with torch.no_grad():
        logits = model(**inputs).logits
        
    probabilities = torch.nn.functional.softmax(logits, dim=-1)[0]
    predicted_ids = torch.argmax(logits, dim=-1)[0]
    
    # 5. Decode phoneme sequence
    detected_phonemes = processor.tokenizer.convert_ids_to_tokens(predicted_ids.tolist())
    
    # Collapse consecutive identical phonemes (CTC decoding)
    collapsed_detected = []
    collapsed_probs = []
    prev_ph = None
    for i, ph in enumerate(detected_phonemes):
        if ph != '[PAD]' and ph != '<s>' and ph != '</s>' and ph != prev_ph:
            # Simple cleanup of token formats (like ' ')
            clean_ph = ph.replace(' ', '')
            if clean_ph:
                collapsed_detected.append(clean_ph)
                collapsed_probs.append(probabilities[i])
        prev_ph = ph
        
    # 6. Align expected phonemes with detected phonemes using DTW
    # fastdtw casts arrays to float internally, so we must map phonemes to integers first
    unique_phonemes = list(set(expected_phonemes + collapsed_detected))
    ph_to_id = {ph: i for i, ph in enumerate(unique_phonemes)}
    
    expected_ids = np.array([ph_to_id[ph] for ph in expected_phonemes]).reshape(-1, 1)
    detected_ids = np.array([ph_to_id[ph] for ph in collapsed_detected]).reshape(-1, 1)
    
    def int_dist(a, b):
        return 0 if a[0] == b[0] else 1
        
    # Run DTW
    if len(expected_ids) == 0 or len(detected_ids) == 0:
        distance, path = 0, []
    else:
        distance, path = fastdtw(expected_ids, detected_ids, dist=int_dist)
    
    # 7. Calculate score
    # Path is a list of tuples: (expected_idx, detected_idx)
    matches = 0
    substitutions = []
    
    feedback = []
    
    for exp_idx, det_idx in path:
        exp_ph = expected_phonemes[exp_idx]
        det_ph = collapsed_detected[det_idx]
        if exp_ph == det_ph:
            matches += 1
        else:
            # We record substituting exp_ph with det_ph
            if (exp_ph, det_ph) not in substitutions:
                substitutions.append((exp_ph, det_ph))
                
    # Basic scoring logic
    max_len = max(len(expected_phonemes), len(collapsed_detected))
    if max_len == 0:
        raw_score = 0
    else:
        # Distance is number of mismatches.
        # Score = 100 * (1 - (distance / max_len))
        raw_score = 100 * (1 - (distance / max_len))
        
    score = max(0, min(100, int(raw_score)))
    
    # Generate feedback
    if not word_detected:
        feedback.append(f"We heard '{transcript}', but expected '{target_word}'.")
        
    if score >= 90:
        feedback.append("Excellent pronunciation!")
    else:
        for exp, det in substitutions:
            feedback.append(f"The /{exp}/ sound was pronounced more like /{det}/.")
            
    # Remove duplicates from feedback
    feedback = list(dict.fromkeys(feedback))

    return {
        "score": score,
        "target_word": target_word,
        "recognized_word": transcript,
        "word_detected": word_detected,
        "expected_phonemes": expected_phonemes,
        "detected_phonemes": collapsed_detected,
        "feedback": feedback
    }
