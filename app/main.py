from contextlib import asynccontextmanager
from fastapi import FastAPI
from transformers import Wav2Vec2Processor, Wav2Vec2ForCTC
from dotenv import load_dotenv

import os

# Load environment variables
load_dotenv()

# We will store loaded models here to be accessed by routers
ml_models = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the ML models ONCE at startup
    print("Loading Wav2Vec2-Phoneme model...")
    
    # We use a popular fine-tuned phoneme recognition model.
    # Note: Depending on the specific model, the output vocabulary is usually IPA.
    model_id = "vitouphy/wav2vec2-xls-r-300m-phoneme"
    
    processor = Wav2Vec2Processor.from_pretrained(model_id)
    model = Wav2Vec2ForCTC.from_pretrained(model_id)
    
    # Move to GPU if available (we will keep it simple and use CPU for prototype unless cuda is available)
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    
    ml_models["wav2vec2_processor"] = processor
    ml_models["wav2vec2_model"] = model
    ml_models["device"] = device
    
    print(f"Model loaded successfully on {device}!")
    
    yield
    
    # Clean up resources on shutdown
    ml_models.clear()
    print("Models unloaded.")


app = FastAPI(lifespan=lifespan, title="Pronunciation Practice ML Backend")

# We import the router down here to avoid circular imports if route.py needs to access ml_models
from app.route.route import router as api_router

app.include_router(api_router)

@app.get("/")
def read_root():
    return {"message": "Pronunciation Practice API is running."}
