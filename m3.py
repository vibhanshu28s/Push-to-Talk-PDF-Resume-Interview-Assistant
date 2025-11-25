import ssl
import urllib3
import os
import requests
import speech_recognition as sr
import threading
import time
import fitz  # PyMuPDF for PDF parsing
import re
import sounddevice as sd
import soundfile as sf
from pynput import keyboard
from threading import Thread, Lock
import numpy as np
import atexit

# Disable SSL verification warnings
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class PushToTalkInterviewAssistant:
    def __init__(self):
        # API settings
        self.groq_api_key = "YOUR_API_KEY"
        self.groq_url = "Your_Groq_URL"

        # Speech recognition
        self.recognizer = sr.Recognizer()
        self.microphone = None

        # Audio recording setup
        self.samplerate = 16000
        self.channels = 1

        # Recording control
        self.is_recording = False
        self.is_running = False
        self.recording_thread = None
        self.audio_frames = []
        self.processing_lock = Lock()

        # Resume info store
        self.resume_info = {}

        self.toggle_key = keyboard.Key.space

        atexit.register(self.cleanup)

    def cleanup(self):
        with self.processing_lock:
            self.is_recording = False
            self.is_running = False

    def extract_pdf_text(self, pdf_path):
        try:
            if not os.path.exists(pdf_path):
                print(f"❌ File not found: {pdf_path}")
                return ""

            doc = fitz.open(pdf_path)
            full_text = ""

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()
                full_text += text + "\n"

            doc.close()
            return full_text.strip()

        except Exception as e:
            print(f"❌ Error extracting PDF text: {e}")
            return ""

    def parse_basic_info(self, text):
        try:
            if not text.strip():
                print("❌ No text to parse")
                return False

            self.resume_info = {
                'full_text': text,
                'name': self.find_name(text),
                'email': self.find_email(text),
                'phone': self.find_phone(text),
                'skills': self.find_skills(text)
            }
            return True
        except Exception as e:
            print(f"❌ Error parsing resume: {e}")
            return False

    def find_name(self, text):
        lines = [line.strip() for line in text.split('\n')[:15] if line.strip()]
        for line in lines:
            words = line.split()
            if 2 <= len(words) <= 3 and all(
                word.replace('.', '').replace(',', '').isalpha() and len(word) > 1
                for word in words
            ):
                if not any(header in line.upper() for header in ['RESUME', 'CV', 'CONTACT', 'EMAIL', 'PHONE']):
                    return line
        return "Candidate"

    def find_email(self, text):
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(email_pattern, text)
        return match.group() if match else "email@example.com"

    def find_phone(self, text):
        phone_patterns = [
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            r'\(\d{3}\)\s?\d{3}[-.]?\d{4}',
            r'\+\d{1,3}\s?\d{3,4}[-.]?\d{3,4}[-.]?\d{4}'
        ]
        for pattern in phone_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group()
        return "Phone not found"

    def find_skills(self, text):
        skills_patterns = [
            r'SKILLS?\s*:?\s*(.*?)(?=\n[A-Z]{3,}|\n\n|\Z)',
            r'TECHNICAL SKILLS?\s*:?\s*(.*?)(?=\n[A-Z]{3,}|\n\n|\Z)',
            r'COMPETENCIES\s*:?\s*(.*?)(?=\n[A-Z]{3,}|\n\n|\Z)'
        ]
        for pattern in skills_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                skills_text = match.group(1)
                skills = re.split(r'[,•\n\|;]', skills_text)
                skills = [s.strip() for s in skills if s.strip() and 2 < len(s.strip()) < 50 and not s.strip().isdigit()]
                return skills[:12] if skills else ["Skills not found"]
        return ["Skills not found"]

    def show_parsed_info(self):
        print("\n" + "=" * 50)
        print("📋 PARSED RESUME INFO")
        print("=" * 50)
        print(f"👤 Name: {self.resume_info.get('name', 'N/A')}")
        print(f"📧 Email: {self.resume_info.get('email', 'N/A')}")
        print(f"📱 Phone: {self.resume_info.get('phone', 'N/A')}")

        skills = self.resume_info.get('skills', [])
        if skills and skills != ["Skills not found"]:
            print(f"\n🛠️ Skills ({len(skills)} found):")
            for i, skill in enumerate(skills, 1):
                print(f"   {i}. {skill}")
        else:
            print("\n🛠️ Skills: Not clearly identified in resume")
        print("=" * 50)

    def create_resume_context(self):
        if not self.resume_info:
            return "You are helping with interview preparation."

        name = self.resume_info.get('name', 'the candidate')
        skills = self.resume_info.get('skills', [])
        full_text = self.resume_info.get('full_text', '')

        context = f"""You are helping {name} prepare for interviews.

CANDIDATE INFO:
Name: {name}
Email: {self.resume_info.get('email', 'N/A')}

SKILLS: {', '.join(skills[:8]) if skills != ['Skills not found'] else 'Various professional skills'}

RESUME CONTENT (excerpt):
{full_text[:800]}...

INSTRUCTIONS:
- Answer interview questions based on this candidate's resume
- Use first person ("I have experience with...")
- Reference their actual skills and background
- Be professional and confident
- Keep answers concise (2-3 sentences)
- If something isn't in the resume, acknowledge honestly but show willingness to learn
"""
        return context

    def get_ai_answer(self, question):
        try:
            headers = {
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json"
            }
            context = self.create_resume_context()

            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": context},
                    {"role": "user", "content": f"Interview question: {question}\n\nProvide a concise, professional answer in 2-3 sentences."}
                ],
                "max_tokens": 300,
                "temperature": 0.7
            }
            response = requests.post(self.groq_url, headers=headers, json=payload, verify=False, timeout=15)

            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            else:
                print(f"⚠️ API Error: {response.status_code}")
                return self.get_basic_answer(question)
        except Exception as e:
            print(f"⚠️ AI Error: {e}")
            return self.get_basic_answer(question)

    def get_basic_answer(self, question):
        if not self.resume_info:
            return "I'd be happy to discuss this further. Could you tell me more about what you're looking for?"

        name = self.resume_info.get('name', 'I')
        skills = self.resume_info.get('skills', [])
        ql = question.lower()

        if "tell me about yourself" in ql or "introduce yourself" in ql:
            ans = f"I'm {name}, a professional with experience in my field."
            if skills and skills != ["Skills not found"]:
                ans += f" My key skills include {', '.join(skills[:3])}."
            return ans + " I'm excited about this opportunity and eager to contribute."

        if "skills" in ql or "technical" in ql:
            if skills and skills != ["Skills not found"]:
                return f"My key technical skills include {', '.join(skills[:5])}. I'm always eager to learn new technologies."
            return "I have various technical and professional skills and I am eager to learn more."

        if "experience" in ql:
            return "I have experience working on diverse projects and approach challenges professionally."

        if "weakness" in ql:
            return "Sometimes I focus too much on details but have learned balancing quality and deadlines."

        if "strength" in ql:
            return "My strengths include problem-solving, attention to detail, and teamwork."

        return "That's a great question. I would approach it professionally and systematically."

    def record_audio(self):
        try:
            self.audio_frames = []
            print("🎤 Recording started... Press SPACEBAR again to stop.")

            def callback(indata, frames, time_, status):
                if status:
                    print(f"⚠️ Recording status: {status}")
                self.audio_frames.append(indata.copy())

            with sd.InputStream(samplerate=self.samplerate, channels=self.channels, callback=callback):
                while self.is_recording and self.is_running:
                    sd.sleep(100)
        except Exception as e:
            print(f"❌ Recording error: {e}")
            self.is_recording = False

    def save_and_process_audio(self):
        if not self.audio_frames:
            print("❌ No audio recorded.")
            return
        try:
            audio_array = np.concatenate(self.audio_frames, axis=0)
            temp_filename = f"temp_question_{int(time.time() * 1000)}.wav"
            sf.write(temp_filename, audio_array, self.samplerate)

            print("🔄 Converting speech to text...")
            with sr.AudioFile(temp_filename) as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
                audio_data = self.recognizer.record(source)

            try:
                question = self.recognizer.recognize_google(audio_data, language='en-US')
                print(f"❓ Question: '{question}'")

                if question.strip():
                    answer = self.get_ai_answer(question.strip())
                    print("\n💡 **Answer:**")
                    print("─" * 50)
                    print(answer)
                    print("─" * 50)
                else:
                    print("❌ No question detected.")
            except sr.UnknownValueError:
                print("❌ Couldn't understand the audio. Please speak more clearly.")
            except sr.RequestError as e:
                print(f"❌ Speech recognition error: {e}")

        finally:
            try:
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
            except Exception:
                pass

    def start_recording(self):
        with self.processing_lock:
            if self.is_recording:
                return
            self.is_recording = True

        self.record_audio()

    def stop_recording(self):
        with self.processing_lock:
            if not self.is_recording:
                return
            self.is_recording = False

        print("⏹️ Recording stopped, processing...")
        self.save_and_process_audio()
        print("\n🎯 Ready for next question! Press SPACEBAR to start recording, or 'q' to quit")

    def on_key_press(self, key):
        try:
            if not self.is_running:
                return False

            if key == self.toggle_key:
                if not self.is_recording:
                    print("🟢 Starting recording...")
                    self.recording_thread = Thread(target=self.start_recording)
                    self.recording_thread.daemon = True
                    self.recording_thread.start()
                else:
                    print("🔴 Stopping recording...")
                    self.stop_recording()

            elif hasattr(key, 'char') and key.char == 'q':
                print("\n👋 Quitting...")
                self.is_running = False
                return False

        except AttributeError:
            pass
        except Exception as e:
            print(f"⚠️ Key press error: {e}")

    def start_toggle_mode(self):
        print("\n🎯 TOGGLE RECORDING MODE")
        print("=" * 60)
        print("📝 Instructions:")
        print("  • Press SPACEBAR once to START recording")
        print("  • Press SPACEBAR again to STOP recording and get answer")
        print("  • Press 'q' to quit anytime")
        print("  • Speak clearly after starting recording")
        print("=" * 60)
        print("\n🎙️ Ready! Press SPACEBAR to start your first question...")

        self.is_running = True

        try:
            listener = keyboard.Listener(on_press=self.on_key_press, suppress=False)
            listener.start()

            while self.is_running:
                time.sleep(0.1)

            listener.stop()

        except KeyboardInterrupt:
            print("\n🛑 Interrupted by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("💡 Try running as administrator if permission errors arise")
        finally:
            self.is_running = False
            if self.is_recording:
                self.stop_recording()

    def start_interview_practice(self):
        print("🚀 Push-to-Talk PDF Resume Interview Assistant (sounddevice version)")
        print("=" * 60)

        try:
            self.microphone = sr.Microphone()
            with self.microphone as source:
                print("🎤 Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            print("✅ Microphone is ready!")
        except Exception as e:
            print(f"❌ Microphone error: {e}")
            return

        while True:
            try:
                pdf_path = input("\n📁 Enter path to your PDF resume (or 'quit' to exit): ").strip()
                if pdf_path.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    return
                if pdf_path.startswith('"') and pdf_path.endswith('"'):
                    pdf_path = pdf_path[1:-1]
                if not os.path.exists(pdf_path):
                    print(f"❌ File not found: {pdf_path}")
                    continue
                if not pdf_path.lower().endswith('.pdf'):
                    print("❌ Please provide a PDF file")
                    continue
                break
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                return

        print(f"\n📖 Processing: {os.path.basename(pdf_path)}")
        text = self.extract_pdf_text(pdf_path)
        if not text:
            print("❌ Could not read PDF content")
            return

        if not self.parse_basic_info(text):
            print("❌ Could not parse resume")
            return

        self.show_parsed_info()

        print("\n✨ Setup complete! Press ENTER to start interview practice...")
        try:
            input()
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            return

        self.start_toggle_mode()


if __name__ == "__main__":
    try:
        print("🎙️ Push-to-Talk PDF Resume Interview Assistant (sounddevice version)")
        print("=" * 60)
        print("Requirements: pip install PyMuPDF requests speechrecognition sounddevice soundfile pynput\n")
        assistant = PushToTalkInterviewAssistant()
        assistant.start_interview_practice()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except ImportError as e:
        print(f"\n❌ Missing required package: {e}")
        print("Install with:\npip install PyMuPDF requests speechrecognition sounddevice soundfile pynput")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        print("\n🏁 Program ended")
