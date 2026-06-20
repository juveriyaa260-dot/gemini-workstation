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
from flask import send_from_directory

load_dotenv()

app = Flask(__name__)

# -------------------------------------------------------------
# MULTI-KEY CLIENT POOL & QUOTA TRACKER INITIALIZATION
# -------------------------------------------------------------
gemini_clients = []
quota_tracker = {}

# Expected capacity limit per key
DEFAULT_MAX_QUOTA = 1500 

for i in range(1, 6):
    key = os.getenv(f"GEMINI_API_KEY_{i}")
    if key:
        client_instance = genai.Client(api_key=key)
        gemini_clients.append({"index": i, "client": client_instance})
        # Track raw usage dynamically in-memory
        quota_tracker[i] = {
            "used": 0,
            "max": DEFAULT_MAX_QUOTA
        }

current_client_index = 0
print(f"Loaded {len(gemini_clients)} native Gemini API cluster clients with active quota meters.")


def evaluate_emc2_throttling(text_payload, history, images):
    """
    Returns the max output tokens to allow for a response.
    Gemini 2.5 Flash supports up to 8192 output tokens.
    """
    return 8192

def extract_youtube_id(url):
    """
    Extracts the 11-character YouTube video ID from various URL patterns.
    """
    pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def download_youtube_audio_bytes(video_url):
    """
    PRO FEATURE: Downloads the audio track of a YouTube video into a 
    temporary space, reads raw binary data, and cleans up local storage.
    """
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
        # Handle extension translation applied by the FFmpeg extractor postprocessor
        audio_path = os.path.splitext(filename)[0] + '.m4a'
        
        if os.path.exists(audio_path):
            with open(audio_path, 'rb') as f:
                audio_bytes = f.read()
            # Immediately scrub file footprint from host system disk
            try:
                os.remove(audio_path)
            except OSError:
                pass
            return audio_bytes, "audio/m4a"
            
    raise FileNotFoundError("Audio extraction subsystem track failure through yt-dlp.")

def transform_to_native_contents(history, text, file_context, images=None, preferences=None):
    current_year = datetime.datetime.now().year
    current_date = datetime.datetime.now().strftime("%B %d, %Y")
    
    base_system_prompt = (
        "You are an elite, natural multi-modal AI collaborator running on Gemini 2.5 Flash. "
        "Engage in conversations cleanly and organically without arbitrary prefixes or bullet tags. "
        "Only utilize structural Markdown, lists, or headers when explicitly summarizing documents, "
        "visualizing files, or responding to complex technical data.\n\n"
        "CRITICAL MARKDOWN CODE RULES:\n"
        "Whenever you output code blocks, scripts, styles (CSS), markup (HTML), or technical configurations, "
        "you MUST enclose them inside standard Markdown code fences specifying the programming language tag "
        "(e.g. ```html, ```css, ```javascript, ```python, or ```bash). Do not output loose, unwrapped "
        "markup or code snippets into your text replies as it breaks the frontend parser.\n\n"
        "AUDIO ANALYSIS RULES:\n"
        "When processing video/audio files, perform high-fidelity multi-modal understanding. "
        "Deduce information natively from spoken word patterns, vocal variations, and presentation structure. "
        "You have structural capabilities to analyze layout pauses, determine structural speakers (Speaker 1, Speaker 2), "
        "detect emotional inflection, and generate timestamps.\n\n"
        f"[TEMPORAL ANCHOR]: Today's current date is officially {current_date}. The current year is {current_year}. "
        "You have live access to Google Search Grounding tools. If a query refers to real-time events, "
        "breaking news, or parameters beyond your original training threshold, execute a web search instantly."
    )
    
    if preferences:
        profile_segments = []
        if preferences.get("nickname"): 
            profile_segments.append(f"- Call the user by this name: {preferences['nickname']}")
        if preferences.get("occupation"): 
            profile_segments.append(f"- User's Occupation/Profession: {preferences['occupation']}")
        if preferences.get("about"): 
            profile_segments.append(f"- User Interests & background details: {preferences['about']}")
        if preferences.get("instructions"): 
            profile_segments.append(f"- SYSTEM BEHAVIOR/STYLE RULES AND CUSTOM INSTRUCTIONS: {preferences['instructions']}")
            
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
            current_parts.append(
                types.Part.from_bytes(data=img_bytes, mime_type=detected_mime_type)
            )
            
    contents.append(types.Content(role="user", parts=current_parts))
    return base_system_prompt, contents

@app.route("/")
def home():
    return render_template("index.html")

    @app.route("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json")

@app.route("/sw.js")
def service_worker():
    return send_from_directory("static", "sw.js")

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
            return jsonify({"success": False, "error": "Empty workspace prompt detected."}), 400

        # --- LIVE PRO YOUTUBE AUDIO PIPELINE INTERCEPTOR ---
        youtube_url_match = re.search(r'(https?://(?:www\.)?(?:youtube\.com|youtu\.be)/\S+)', text, re.IGNORECASE)
        native_audio_part = None
        
        if youtube_url_match:
            target_video_url = youtube_url_match.group(1)
            print(f"[PRO ANALYZER] Isolating audio payload tracking stream vector for: {target_video_url}")
            try:
                raw_audio_stream, mime_type = download_youtube_audio_bytes(target_video_url)
                # Formulate a native audio injection part token for the payload
                native_audio_part = types.Part.from_bytes(data=raw_audio_stream, mime_type=mime_type)
                
                # Override generic instructions if user pasted purely a bare URL link string
                if len(text.strip()) <= 45:
                    text = "Perform an exhaustive analysis on the attached audio track. Highlight explicit structural speaker detection indices, vocal variations, core takeaways, and time chapters."
            except Exception as yt_err:
                print(f"💥 Audio compilation extraction failure sequence: {str(yt_err)}")
                return jsonify({"success": False, "error": f"Audio parsing initialization failure: {str(yt_err)}"}), 500

        if not gemini_clients:
            return jsonify({"success": False, "error": "No Gemini API keys configured in .env."}), 500

        total_available_clients = len(gemini_clients)

        # --- LIVE NATIVE IMAGE GENERATION TIMEOUT PIPELINE ---
        if text.lower().startswith("/image "):
            image_prompt = text[7:].strip()
            if not image_prompt:
                return jsonify({"success": False, "error": "Please provide a description for the image after /image."}), 400
            
            for attempt in range(total_available_clients):
                target_node = gemini_clients[current_client_index % total_available_clients]
                active_client = target_node["client"]
                key_number = target_node["index"]
                
                try:
                    print(f"[IMAGE ROUTER] Attempting live asset generation via Key Slot #{key_number}...")
                    response = active_client.models.generate_content(
                        model="gemini-3.1-flash-image",
                        contents=[image_prompt],
                    )
                    
                    b64_encoded_asset = None
                    for part in response.parts:
                        if part.inline_data is not None:
                            b64_encoded_asset = base64.b64encode(part.inline_data.data).decode('utf-8')
                            break
                    
                    if not b64_encoded_asset:
                        raise ValueError("API omitted inline image payload data.")
                    
                    quota_tracker[key_number]["used"] = min(quota_tracker[key_number]["used"] + 1, quota_tracker[key_number]["max"])
                    
                    img_data_uri = f"data:image/png;base64,{b64_encoded_asset}"
                    markdown_reply = (
                        f"### Live Gemini Engine Generation\n"
                        f"Here is your live production asset matching the parameters of your input vector:\n\n"
                        f"![{image_prompt}]({img_data_uri})\n\n"
                        f" *🎨 Generated via **Live Gemini-3.1-Flash-Image Cluster** | Served via Slot #{key_number}*"
                    )
                    
                    return jsonify({
                        "success": True,
                        "reply": markdown_reply,
                        "was_searched": False,
                        "query_used": f"Served by Live Gemini-Image Key Slot {key_number}"
                    })
                except Exception as img_err:
                    print(f"⚠️ Image Key Slot #{key_number} encountered failure: {str(img_err)}")
                    current_client_index = (current_client_index + 1) % total_available_clients
                    continue
            
            return jsonify({"success": False, "error": "All allocated Gemini key slots returned exhaustion errors for image generation."}), 500

        # --- TEXT & MULTIMODAL GENERATION WITH LIVE GOOGLE SEARCH GROUNDING ---
        computed_token_limit = evaluate_emc2_throttling(text, history, images)
        system_instruction, contents_payload = transform_to_native_contents(
            history, text, file_context, images, preferences
        )
        
        # INJECT NATIVE MULTIMODAL AUDIO EXTRACT INTO USER CONTEXT SEGMENT
        if native_audio_part:
            contents_payload[-1].parts.append(native_audio_part)

        for attempt in range(total_available_clients):
            target_node = gemini_clients[current_client_index % total_available_clients]
            active_client = target_node["client"]
            key_number = target_node["index"]
            
            try:
                print(f"[API ROUTER] Attempting execution via Key Slot #{key_number} with Live Search...")
                response = active_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=contents_payload,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        tools=[{"google_search": {}}],
                        max_output_tokens=computed_token_limit,
                        temperature=0.5
                    )
                )
                
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
                    "reply": response.text,
                    "was_searched": was_searched,
                    "query_used": f"Served by Key Slot {key_number} (Live Search Grounded)"
                })
                
            except Exception as api_err:
                print(f"⚠️ Key Slot #{key_number} failed with error: {str(api_err)}")
                current_client_index = (current_client_index + 1) % total_available_clients
                continue
                
        return jsonify({
            "success": False, 
            "error": "All 5 allocated Gemini Key interfaces failed generation validation sequences consecutively."
        }), 500
        
    except Exception as e:
        return jsonify({"success": False, "error": f"Core Array Gateway Error: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
