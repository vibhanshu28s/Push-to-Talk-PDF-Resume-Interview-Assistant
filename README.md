# Push-to-Talk-PDF-Resume-Interview-Assistant
An AI-powered real-time interview preparation tool that listens to interviewer questions via speech recognition and provides instant, personalized answers based on your resume.​

# Features

  - Resume Parsing: Automatically extracts candidate information (name, email, phone, skills) from PDF resumes using PyMuPDF​

  - Push-to-Talk Recording: Simple spacebar toggle for starting/stopping audio capture with sounddevice library​

  - Speech-to-Text: Converts spoken interview questions to text using Google Speech Recognition API​

  - AI-Powered Responses: Generates professional, contextual answers using Groq's LLaMA 3.3 70B model tailored to your resume​

  - Real-Time Processing: Processes questions and delivers answers within seconds for seamless interview practice​

  - Fallback Responses: Provides basic answers when API calls fail, ensuring continuous functionality​

# Technology Stack
  - Python 3.x with key libraries including SpeechRecognition, sounddevice, soundfile, PyMuPDF, pynput, and requests for API integration.​

# How It Works
  - The assistant parses your PDF resume, extracts relevant information, then enters toggle recording mode where pressing spacebar starts audio capture of interview questions. It converts speech to text, sends the question along with resume context to the AI API, and displays a professional first-person answer in 2-3 sentences.

# How to Use
  1. Clone the Repository.
  2. Run "    pip install -r requirements.txt".
  3. Setup: Add your Groq API key and place your resume PDF in the project directory​
  4. Run: Execute python m3.py and enter your PDF filename when prompted​
  5. Record Questions: Press and hold spacebar to start recording an interview question, release to stop​
  6. Get Answers: The AI will transcribe the question and generate a personalized answer based on your resume context​
  7. Exit: Type 'quit' or 'exit' when finished​
  8. The assistant automatically parses your resume on startup and stays ready to help you practice interview responses in real-time.​
