import os
import requests
import json
import base64
import time
import datetime
import re
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from youtube_transcript_api import YouTubeTranscriptApi

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

def get_youtube_transcript(video_id):
    """
    Fetches plain text transcripts with multi-language fallback arrays.
    """
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'es', 'fr', 'de'])
        full_transcript = " ".join([item['text'] for item in transcript_list])
        return full_transcript
    except Exception as e:
        return f"Could not retrieve automatic transcript metadata for video {video_id}. Error details: {str(e)}"

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

        # --- LIVE YOUTUBE ANALYSER PIPELINE INTERCEPTOR ---
        detected_video_id = extract_youtube_id(text)
        if detected_video_id:
            print(f"[YOUTUBE DETECTOR] Extracting transcript asset for Video ID: {detected_video_id}...")
            video_transcript = get_youtube_transcript(detected_video_id)
            
            # Inject structural transcript text into the file context space
            file_context += f"\n\n--- AUTO-EXTRACTED YOUTUBE TRANSCRIPT (ID: {detected_video_id}) ---\n{video_transcript}\n\n"
            
            # Fallback text instruction configuration if user dropped raw URL link blindly
            if len(text) <= 45:
                text = "Please clean up, digest, and summarize the attached video transcript asset comprehensively."

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
    # Use the port assigned by the cloud provider, fallback to 5000 locally
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)