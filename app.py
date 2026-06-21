import os
import requests
import json
import base64
import time
import datetime
import re
import tempfile
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
import yt_dlp

load_dotenv()

app = Flask(__name__)

# -------------------------------------------------------------
# MULTI-KEY CLIENT POOL & QUOTA TRACKER INITIALIZATION
# -------------------------------------------------------------
gemini_clients = []
quota_tracker = {}
DEFAULT_MAX_QUOTA = 1500 

for i in range(1, 6):
    key = os.getenv(f"GEMINI_API_KEY_{i}")
    if key:
        client_instance = genai.Client(api_key=key)
        gemini_clients.append({"index": i, "client": client_instance})
        quota_tracker[i] = {"used": 0, "max": DEFAULT_MAX_QUOTA}

current_client_index = 0
print(f"Loaded {len(gemini_clients)} Gemini cluster clients.")


def evaluate_emc2_throttling(text_payload, history, images):
    return 1024

def extract_youtube_id(url):
    pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def download_youtube_audio_bytes(video_url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
            'preferredquality': '128',
        }],
        'outtmpl': os.path.join(tempfile.gettempdir(), '%(id)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        filename = ydl.prepare_filename(info)
        audio_path = os.path.splitext(filename)[0] + '.m4a'
        if os.path.exists(audio_path):
            with open(audio_path, 'rb') as f:
                audio_bytes = f.read()
            try:
                os.remove(audio_path)
            except OSError:
                pass
            return audio_bytes, "audio/m4a"
    raise FileNotFoundError("Audio extraction subsystem track failure through yt-dlp.")


def transform_to_native_contents(history, text, file_context, images=None, preferences=None):
    base_system_prompt = (
        "You are an elite, natural multi-modal AI collaborator running on Gemini 2.5 Flash.\n\n"
        "RESPONSE STYLE RULES:\n"
        "For simple factual questions:\n"
        "- Answer in 1-3 short paragraphs.\n"
        "- Give the direct answer first.\n"
        "- Keep answers concise.\n"
        "- Avoid unnecessary headings or bullet points.\n"
    )
    
    if preferences:
        profile_segments = []
        if preferences.get("nickname"): profile_segments.append(f"- Call the user by this name: {preferences['nickname']}")
        if preferences.get("occupation"): profile_segments.append(f"- User's Occupation/Profession: {preferences['occupation']}")
        if preferences.get("about"): profile_segments.append(f"- User Interests & background details: {preferences['about']}")
        if preferences.get("instructions"): profile_segments.append(f"- SYSTEM BEHAVIOR/STYLE RULES AND CUSTOM INSTRUCTIONS: {preferences['instructions']}")
        if profile_segments:
            base_system_prompt += "\n\n[USER PROFILE & CUSTOM RESPONSE INSTRUCTIONS]\n" + "\n".join(profile_segments)
    
    if file_context:
        base_system_prompt += f"\n\n[UPLOADED FILE CONTEXT]\n{file_context}\n"
        
    contents = []
    for msg in history:
        role = "user" if msg.get("sender") == "user" else "model"
        if "msg-text-body" in msg.get("text", ""):
            try:
                soup = BeautifulSoup(msg.get("text", ""), "html.parser")
                text_el = soup.find('div', class_='msg-text-body')
                clean_text = text_el.get_text() if text_el else soup.get_text()
            except Exception:
                clean_text = msg.get("text", "")
        else:
            clean_text = BeautifulSoup(msg.get("text", ""), "html.parser").get_text()
            
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=clean_text)]))
        
    current_content_text = text if text else "Analyze the provided operational workspace assets."
    current_parts = [types.Part.from_text(text=current_content_text)]
    
    if images and len(images) > 0:
        for img in images:
            img_bytes = base64.b64decode(img.get('base64', ''))
            detected_mime_type = img.get('type', 'image/jpeg')
            current_parts.append(types.Part.from_bytes(data=img_bytes, mime_type=detected_mime_type))
            
    contents.append(types.Content(role="user", parts=current_parts))
    return base_system_prompt, contents


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/quota_status", methods=["GET"])
def get_quota_status():
    return jsonify({"success": True, "tracker": quota_tracker})

@app.route("/chat", methods=["POST"])
def chat():
    global current_client_index
    
    try:
        data = request.get_json() or {}
        text = data.get("text", "").strip()
        history = data.get("history", [])
        file_context = data.get("file_context", "").strip()
        images = data.get("images", [])
        preferences = data.get("preferences", {})

        if not text and not file_context and not images:
            print("[WARN] Empty workspace submission rejected.")
            return jsonify({"success": False, "error": "Empty workspace prompt detected."}), 400

        # --- LIVE YOUTUBE AUDIO PIPELINE INTERCEPTOR ---
        youtube_url_match = re.search(r'(https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+)', text, re.IGNORECASE)
        native_audio_part = None
        
        if youtube_url_match:
            target_video_url = youtube_url_match.group(1)
            try:
                print(f"[YOUTUBE EXTRACTOR] Extracting audio stream track from: {target_video_url}")
                raw_audio_stream, mime_type = download_youtube_audio_bytes(target_video_url)
                native_audio_part = types.Part.from_bytes(data=raw_audio_stream, mime_type=mime_type)
                if len(text.strip()) <= 45:
                    text = "Perform an exhaustive analysis on the attached audio track."
            except Exception as yt_err:
                print(f"[ERROR] Youtube processing failure: {str(yt_err)}")
                return jsonify({"success": False, "error": f"Audio parsing initialization failure: {str(yt_err)}"}), 500

        if not gemini_clients:
            print("[CRITICAL] Gemini Configuration Error: No client instances initialized inside workspace pipeline.")
            return jsonify({"success": False, "error": "No Gemini API keys configured in .env."}), 500

        total_available_clients = len(gemini_clients)
        computed_token_limit = evaluate_emc2_throttling(text, history, images)
        system_instruction, contents_payload = transform_to_native_contents(
            history, text, file_context, images, preferences
        )
        
        if native_audio_part:
            contents_payload[-1].parts.append(native_audio_part)

        # Standard Text Chat Generation Sequence
        for attempt in range(total_available_clients):
            target_node = gemini_clients[current_client_index % total_available_clients]
            active_client = target_node["client"]
            key_number = target_node["index"]
            
            try:
                print(f"[GEMINI ROUTER] Routing chat to Cluster Client Key Slot #{key_number}...")
                response = active_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=contents_payload,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        tools=[{"google_search": {}}],
                        max_output_tokens=computed_token_limit,
                        temperature=0.3
                    )
                )
                
                if not response or not response.text:
                    raise Exception("Received empty response string payload from layout generation node.")

                ai_reply_text = response.text
                quota_tracker[key_number]["used"] = min(quota_tracker[key_number]["used"] + 1, quota_tracker[key_number]["max"])
                
                was_searched = False
                try:
                    metadata = response.candidates[0].grounding_metadata
                    if metadata and metadata.web_search_queries:
                        was_searched = True
                except Exception:
                    pass

                return jsonify({
                    "success": True,
                    "reply": ai_reply_text,
                    "was_searched": was_searched,
                    "query_used": f"Served by Key Slot {key_number}",
                    "is_image_creation": False
                })
                
            except Exception as api_err:
                print(f"[WARN] Cluster Key Slot #{key_number} failed: {str(api_err)}")
                current_client_index = (current_client_index + 1) % total_available_clients
                continue
                
        return jsonify({
            "success": False, 
            "error": "All allocated Gemini generation slots returned framework execution connectivity errors."
        }), 500
        
    except Exception as e:
        print(f"[EXCEPTIONAL GATEWAY ERROR] Pipeline fault encountered: {str(e)}")
        return jsonify({"success": False, "error": f"Core Array Gateway Error: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
