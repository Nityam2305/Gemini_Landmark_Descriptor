import streamlit as st
import google.generativeai as genai
from PIL import Image
import os
import wikipediaapi
import re
import requests
from dotenv import load_dotenv
from gtts import gTTS
import tempfile

# Load environment variables
load_dotenv()
GEN_API_KEY = os.getenv("GOOGLE_API_KEY")

# Configure AI API
genai.configure(api_key=GEN_API_KEY)

# Initialize Wikipedia API in English
wiki_wiki = wikipediaapi.Wikipedia(
    user_agent="NeuralVoyagersBot/1.0 (Contact: your-email@example.com)",
    language="en")

# Function to clean extracted names
def clean_name(text):
    text = re.sub(r"[*]+", "", text).strip()
    text = re.split(r"\(|-", text)[0].strip()
    return text

# Function to process image and get landmark description
def get_landmark_description(image_data, language="English"):
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = """
    You are an expert in geography and tourism. Analyze the image and identify the landmark shown.
    Provide:
    1. Name (in English)
    2. Location (City, Country)
    3. Historical significance
    4. Dimensions
    5. Nearby places (maximum 5, separated by commas).
    Respond in English with clear section headers like "Name:", "Location:", "Historical significance:", "Dimensions:", "Nearby places:".
    """
    try:
        response = model.generate_content([prompt, image_data[0]])
        english_response = response.text
        
        landmark_name, location = extract_landmark_and_location(english_response)
        nearby_places = extract_nearby_places(english_response)
        
        if language == "English":
            return english_response, landmark_name, location, nearby_places
        
        translate_prompt = f"""
        Translate the following text to {language}. Keep all proper nouns (e.g., names of people, places, landmarks) in English unchanged:
        {english_response}
        """
        translated_response = model.generate_content(translate_prompt).text
        return translated_response, landmark_name, location, nearby_places
    except Exception as e:
        return f"Error generating description: {str(e)}", "Unknown", None, []

# Extract landmark name and location from AI response
def extract_landmark_and_location(response_text):
    name_pattern = re.search(r"Name:\s*(.*)", response_text, re.IGNORECASE)
    location_pattern = re.search(r"Location:\s*(.*)", response_text, re.IGNORECASE)
    name = clean_name(name_pattern.group(1)) if name_pattern else "Unknown"
    location = clean_name(location_pattern.group(1)) if location_pattern else None
    return name, location

# Extract nearby places from AI response (always in English)
def extract_nearby_places(response_text):
    nearby_places_pattern = re.search(r"Nearby places:?\s*(.*)", response_text, re.IGNORECASE | re.DOTALL)
    if nearby_places_pattern:
        places_text = nearby_places_pattern.group(1).strip()
        places = re.split(r",|\n", places_text)
        return [clean_name(place) for place in places if place.strip() and ":" not in place][:5]
    return []

# Get Wikipedia link (always in English)
def get_wikipedia_link(place):
    try:
        page = wiki_wiki.page(place)
        if page.exists():
            return page.fullurl
        return None
    except requests.exceptions.RequestException:
        return None

# Convert location to Google Maps link
def get_google_maps_link(name, location):
    query = f"{name}, {location}" if location else name
    return f"https://www.google.com/maps/search/?api=1&query={query.replace(' ', '+')}"

# Function to generate a detailed itinerary
def generate_itinerary(origin, destination, landmark_name, nearby_places, num_days, language):
    # Suggest cheapest days to fly (Tuesday/Wednesday)
    cheapest_days = "Tuesday or Wednesday"
    
    # Extract city and country from location (e.g., "Agra, India" from "Taj Mahal, Agra, India")
    location_parts = destination.split(", ")
    if len(location_parts) >= 2:
        city = location_parts[-2]  # Second-to-last part is city (e.g., "Agra")
        country = location_parts[-1]  # Last part is country (e.g., "India")
    else:
        city = destination
        country = "Unknown"
    
    # Initialize itinerary
    itinerary = f"""
    **Trip Itinerary from {origin} to {landmark_name}, {city}, {country}:**
    - **Origin:** {origin}
    - **Destination:** {landmark_name}, {city}, {country}
    - **Cheapest Days to Fly:** {cheapest_days}
    - **Number of Days:** {num_days}
    - **Travel Tips:** 
      - Book flights for {cheapest_days} to save on costs.
      - Arrive early at {landmark_name} to avoid crowds, ideally at sunrise.
      - Use local transport in {city} (e.g., auto-rickshaws, metro, or taxis) for affordable travel.
    """
    
    # Day-by-day plan
    itinerary += "\n**Day-by-Day Plan:**\n"
    for day in range(1, num_days + 1):
        if day == 1:
            itinerary += f"- **Day {day}: Travel and Initial Exploration**\n"
            itinerary += f"  - Fly from {origin} to {city}, {country} (arrive by midday if possible).\n"
            itinerary += f"  - Check into your accommodation in {city}.\n"
            itinerary += f"  - Spend the evening exploring local markets or cuisine in {city}.\n"
        elif day == num_days:
            itinerary += f"- **Day {day}: Final Exploration and Departure**\n"
            itinerary += f"  - Visit any remaining nearby attractions or do some souvenir shopping in {city}.\n"
            itinerary += f"  - Depart from {city} back to {origin}.\n"
        else:
            # Distribute nearby places across the days
            places_per_day = len(nearby_places) // (num_days - 2) if num_days > 2 else len(nearby_places)
            start_idx = (day - 2) * places_per_day
            end_idx = start_idx + places_per_day
            day_places = nearby_places[start_idx:end_idx] if nearby_places else []
            
            if day == 2:  # Main landmark visit on Day 2
                itinerary += f"- **Day {day}: Visit {landmark_name}**\n"
                itinerary += f"  - Spend the morning at {landmark_name}, exploring its history and architecture.\n"
                itinerary += f"  - Take a guided tour if available, or hire a local guide for insights.\n"
                if day_places:
                    itinerary += f"  - In the afternoon, visit nearby attractions: {', '.join(day_places)}.\n"
            else:
                itinerary += f"- **Day {day}: Explore Nearby Attractions**\n"
                if day_places:
                    itinerary += f"  - Visit {', '.join(day_places)}.\n"
                    itinerary += f"  - Enjoy local activities (e.g., sightseeing, photography, or cultural experiences).\n"
                else:
                    itinerary += f"  - Explore more of {city}, or revisit {landmark_name} at a different time of day (e.g., sunset).\n"
    
    # Add a Google Maps link for the destination
    itinerary += f"\n- [Plan Your Route on Google Maps](https://www.google.com/maps/dir/?api=1&origin={origin}&destination={landmark_name},+{city},+{country})"
    
    return itinerary

# Function to generate and save speech
def text_to_speech(text, lang="en"):
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # Remove bold text
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
        tts = gTTS(text=text, lang=lang)
        tts.save(temp_audio.name)
        return temp_audio.name

# Initialize session state
if 'landmark_data' not in st.session_state:
    st.session_state.landmark_data = None
if 'itinerary_data' not in st.session_state:
    st.session_state.itinerary_data = None
if 'current_location' not in st.session_state:
    st.session_state.current_location = "Your location here"
if 'num_days' not in st.session_state:
    st.session_state.num_days = 5

# Streamlit UI
st.set_page_config(page_title="Landmark Identifier AI", layout="centered")

# Add custom CSS for tourist-themed background
st.markdown(
    """
    <style>
    /* Tourist-themed background with a subtle world map and travel icons */
    .stApp {
        background: url('https://images.unsplash.com/photo-1501785888041-af3ef285b470?ixlib=rb-4.0.3&auto=format&fit=crop&w=1350&q=80') center/cover no-repeat fixed;
        background-color: rgba(0, 0, 0, 0.3); /* Dark overlay for readability */
        background-blend-mode: overlay;
    }

    /* Ensure text is readable */
    .stApp, h1, p, div, span, a, .stMarkdown, .stText, .stAudio {
        color: #ffffff !important;
        text-shadow: 1px 1px 4px rgba(0, 0, 0, 0.8);
    }

    /* Style for the uploader, selectbox, and button */
    .stFileUploader, .stSelectbox, .stButton {
        background-color: rgba(255, 255, 255, 0.2);
        border-radius: 10px;
        padding: 10px;
        border: 1px solid rgba(255, 255, 255, 0.3);
    }

    /* Style for the image container */
    .stImage img {
        border-radius: 10px;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.5);
        border: 2px solid #ffffff;
    }

    /* Style for links */
    a {
        color: #ffcc00 !important; /* Gold color for a touristy feel */
        text-decoration: none;
        font-weight: bold;
    }
    a:hover {
        text-decoration: underline;
        color: #ffd700 !important;
    }

    /* Center content */
    .stApp > div {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown("""<h1 style='text-align: center;'>🗺️ Landmark Identifier AI</h1>""", unsafe_allow_html=True)

# Input controls centered
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    uploaded_file = st.file_uploader("Upload an image...", type=["jpg", "jpeg", "png"], key="image_uploader")
    language = st.selectbox("Select Language", ["English", "Spanish", "French", "German", "Japanese", "Hindi", "Chinese"], key="language_select")
    if st.button("Identify the Landmark", key="identify_button"):
        st.session_state.itinerary_data = None  # Reset itinerary on new identification
        try:
            image = Image.open(uploaded_file)
            image_data = [{"mime_type": uploaded_file.type, "data": uploaded_file.getvalue()}]
            description, landmark_name, location, nearby_places = get_landmark_description(image_data, language)
            description_lines = description.split('\n')
            mid_point = len(description_lines) // 2
            first_half = '\n'.join(description_lines[:mid_point])
            second_half = '\n'.join(description_lines[mid_point:])
            full_location = f"{landmark_name}, {location}" if location else landmark_name

            # Store in session state
            st.session_state.landmark_data = {
                "image": image,
                "description": description,
                "first_half": first_half,
                "second_half": second_half,
                "landmark_name": landmark_name,
                "location": location,
                "nearby_places": nearby_places,
                "full_location": full_location,
                "language": language
            }
        except Exception as e:
            st.error(f"⚠️ Error: {str(e)}")
            st.session_state.landmark_data = None

# Display landmark data if available
if st.session_state.landmark_data:
    data = st.session_state.landmark_data
    # Display first half of description
    st.write(data["first_half"])

    # Display image in the middle
    col_img, _ = st.columns([1, 2])
    with col_img:
        st.image(data["image"], caption="Uploaded Image", use_container_width=True)

    # Display second half of description
    st.write(data["second_half"])

    # Trip Planning with Itinerary
    st.subheader("Plan a Trip from Your Location")
    current_location = st.text_input("Enter your current location (e.g., 'New York, NY')", 
                                     value=st.session_state.current_location, 
                                     key="current_location_input")
    num_days = st.number_input("Number of days for the trip", 
                               min_value=1, max_value=14, value=st.session_state.num_days, step=1, 
                               key="num_days_input")
    
    # Update session state with inputs
    st.session_state.current_location = current_location
    st.session_state.num_days = num_days

    if st.button("Generate Itinerary", key="generate_itinerary_button"):
        if data["location"]:  # Ensure landmark location is available
            itinerary = generate_itinerary(
                current_location, 
                data["location"],  # Use location (e.g., "Agra, India") instead of full_location
                data["landmark_name"], 
                data["nearby_places"], 
                num_days, 
                data["language"]
            )
            st.session_state.itinerary_data = itinerary
        else:
            st.session_state.itinerary_data = "Unable to plan trip: Landmark location not identified."

    # Display itinerary if available
    if st.session_state.itinerary_data:
        st.write(st.session_state.itinerary_data)

    # Useful Links
    wiki_link = get_wikipedia_link(data["landmark_name"])
    google_maps_link = get_google_maps_link(data["landmark_name"], data["location"])

    if wiki_link:
        st.markdown(f"📖 [Wikipedia: {data['landmark_name']} (English)]({wiki_link})")
    else:
        st.markdown(f"⚠️ Wikipedia page not found for {data['landmark_name']}")

    st.markdown(f"🗺️ [View on Google Maps]({google_maps_link})")

    # Nearby Attractions
    nearby_labels = {
        "English": "Nearby Attractions:",
        "Spanish": "Atracciones cercanas:",
        "French": "Attractions à proximité :",
        "German": "Nahegelegene Sehenswürdigkeiten:",
        "Japanese": "近隣の観光スポット:",
        "Hindi": "नजदीकी आकर्षण:",
        "Chinese": "附近景点:"
    }
    if data["nearby_places"]:
        st.write(nearby_labels.get(data["language"], "Nearby Attractions:"))
        for place in data["nearby_places"]:
            place_wiki_link = get_wikipedia_link(place)
            place_maps_link = get_google_maps_link(place, data["location"])
            wiki_text = f"📖 [Wikipedia (English)]({place_wiki_link})" if place_wiki_link else "⚠️ No Wikipedia"
            maps_text = f"🗺️ [Google Maps]({place_maps_link})"
            st.write(f"🔹 {place} - {wiki_text} | {maps_text}")
    else:
        st.write("⚠️ No nearby attractions found.")

    # Audio Description
    if data["description"] and not data["description"].startswith("Error"):
        lang_code = {'English': 'en', 'Spanish': 'es', 'French': 'fr', 'German': 'de', 'Japanese': 'ja', 'Hindi': 'hi', 'Chinese': 'zh-CN'}.get(data["language"], 'en')
        audio_file = text_to_speech(data["description"], lang=lang_code)
        st.audio(audio_file, format="audio/mp3")