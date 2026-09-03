// Base URL for FastAPI backend
const API_BASE = "http://localhost:8000";

let mediaRecorder;
let audioChunks = [];

// DOM Elements
const targetWordInput = document.getElementById('targetWord');
const recordBtn = document.getElementById('recordBtn');
const statusMsg = document.getElementById('statusMsg');
const resultsSection = document.getElementById('resultsSection');
const scoreCircle = document.getElementById('scoreCircle');
const scoreValue = document.getElementById('scoreValue');
const scoreTitle = document.getElementById('scoreTitle');
const resTargetWord = document.getElementById('resTargetWord');
const resRecognizedWord = document.getElementById('resRecognizedWord');
const feedbackList = document.getElementById('feedbackList');

// Pre-fill input from vocabulary chips
function setWord(word) {
    targetWordInput.value = word;
    // Highlight the active chip (optional micro-interaction)
    document.querySelectorAll('.chip').forEach(chip => chip.style.background = 'rgba(255, 255, 255, 0.8)');
    event.target.style.background = 'var(--primary)';
    event.target.style.color = 'white';
}

// Setup Media Recorder
navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
        mediaRecorder = new MediaRecorder(stream);

        mediaRecorder.ondataavailable = event => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            audioChunks = [];
            await sendAudioToBackend(audioBlob);
        };
    })
    .catch(err => {
        statusMsg.textContent = "Error accessing microphone. Please allow permissions.";
        console.error(err);
    });

// Handle Record Button Clicks
let isRecording = false;

recordBtn.onclick = () => {
    if (!targetWordInput.value.trim()) {
        statusMsg.textContent = "Please enter a target word first!";
        statusMsg.style.color = 'var(--danger)';
        return;
    }
    
    if (!isRecording) {
        // Start Recording
        audioChunks = [];
        mediaRecorder.start();
        isRecording = true;
        
        recordBtn.classList.add('recording');
        recordBtn.querySelector('span').textContent = 'Stop Recording';
        recordBtn.querySelector('i').classList.replace('fa-microphone', 'fa-stop');
        
        statusMsg.textContent = "Listening...";
        statusMsg.style.color = 'var(--danger)';
        resultsSection.classList.add('hidden'); // Hide old results
    } else {
        // Stop Recording
        mediaRecorder.stop();
        isRecording = false;
        
        recordBtn.classList.remove('recording');
        recordBtn.querySelector('span').textContent = 'Start Recording';
        recordBtn.querySelector('i').classList.replace('fa-stop', 'fa-microphone');
        
        statusMsg.textContent = "Processing your pronunciation... 🧠";
        statusMsg.style.color = 'var(--primary)';
    }
};

// Communicate with Backend
async function sendAudioToBackend(audioBlob) {
    const targetWord = targetWordInput.value.trim();
    const mode = document.querySelector('input[name="mode"]:checked').value;
    
    const formData = new FormData();
    formData.append("target_word", targetWord);
    formData.append("audio", audioBlob, "recording.wav");
    
    const endpoint = mode === "individual" ? "/score/individual" : "/score/sentence";
    const url = `${API_BASE}${endpoint}`;

    try {
        const response = await fetch(url, {
            method: "POST",
            body: formData
        });
        
        if (!response.ok) {
            const errText = await response.text();
            throw new Error(`Server returned ${response.status}: ${errText}`);
        }

        const data = await response.json();
        renderResults(data);
        
    } catch (err) {
        console.error(err);
        statusMsg.textContent = `Error: ${err.message}`;
        statusMsg.style.color = 'var(--danger)';
    }
}

// Render Results Dashboard
function renderResults(data) {
    statusMsg.textContent = "Score calculated!";
    statusMsg.style.color = 'var(--success)';
    
    // Unhide results
    resultsSection.classList.remove('hidden');
    
    // Fill basic details
    resTargetWord.textContent = data.target_word;
    resRecognizedWord.textContent = data.recognized_word || data.transcript || "None detected";
    
    // Animate Circular Progress
    const finalScore = data.score || 0;
    animateValue(scoreValue, 0, finalScore, 1000);
    
    // Set color based on score
    let color = 'var(--danger)';
    scoreTitle.textContent = "Needs Practice";
    if (finalScore >= 80) {
        color = 'var(--success)';
        scoreTitle.textContent = "Excellent!";
    } else if (finalScore >= 50) {
        color = '#f59e0b'; // Amber/Yellow
        scoreTitle.textContent = "Good Effort";
    }
    
    // Animate the conic gradient
    let progressStartValue = 0;
    let speed = 10;
    let progress = setInterval(() => {
        progressStartValue++;
        scoreCircle.style.background = `conic-gradient(${color} ${progressStartValue * 3.6}deg, #f1f5f9 0deg)`;
        if (progressStartValue == finalScore || finalScore == 0) {
            clearInterval(progress);
        }
    }, speed);
    
    // Render Feedback
    feedbackList.innerHTML = '';
    if (data.feedback && data.feedback.length > 0) {
        data.feedback.forEach(item => {
            const li = document.createElement('li');
            li.innerHTML = item.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>'); // bolding logic if LLM uses markdown
            feedbackList.appendChild(li);
        });
    } else {
        const li = document.createElement('li');
        li.textContent = "No specific feedback available.";
        feedbackList.appendChild(li);
    }
}

// Number animation helper
function animateValue(obj, start, end, duration) {
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        obj.innerHTML = Math.floor(progress * (end - start) + start);
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}
