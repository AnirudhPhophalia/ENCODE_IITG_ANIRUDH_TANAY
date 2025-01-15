from fastapi import FastAPI, Request, Form
from fastapi.responses import Response
from pydantic import BaseModel
from twilio.rest import Client
from google.cloud import texttospeech, speech
import openai
import pymongo
import os

app = FastAPI() # fastApi app initialize karne ke liye

# Twilio client setup
TWILIO_ACCOUNT_SID = "your_twilio_account_sid"
TWILIO_AUTH_TOKEN = "your_twilio_auth_token"
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# OpenAI setup
openai.api_key = "your_openai_api_key"

# MongoDB setup
MONGO_URI = "your_mongodb_connection_uri"
mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client["ai_phone_agent"]
customers_collection = db["customers"]

# Google TTS and STT setup
tts_client = texttospeech.TextToSpeechClient()
stt_client = speech.SpeechClient()

# Twilio phone number
TWILIO_PHONE_NUMBER = "your_twilio_phone_number"


# initiating call ke liye scheme
class CallRequest(BaseModel):
    phone_number: str
    customer_id: str


# call initiation ke liye route
@app.post("/call-customer")
async def call_customer(request: CallRequest):
    customer = customers_collection.find_one({"_id": request.customer_id})
    if not customer:
        return {"error": "Customer not found"}

    # twilio call initiate karne ke liye
    call = twilio_client.calls.create(
        to=request.phone_number,
        from_=TWILIO_PHONE_NUMBER,
        url="https://your-server-url/twilio-webhook"
    )
    return {"message": "Call initiated", "call_sid": call.sid}


# Twilio webhook for processing responses
@app.post("/twilio-webhook")
async def twilio_webhook(
    SpeechResult: str = Form(None), CallSid: str = Form(None)
):
    # Process user input
    if SpeechResult:
        response_text = generate_response(SpeechResult)
        audio_url = synthesize_speech(response_text)

        # Generate TwiML response
        twiml = f"""
        <Response>
            <Play>{audio_url}</Play>
            <Redirect>https://your-server-url/twilio-webhook</Redirect>
        </Response>
        """
        return Response(content=twiml, media_type="application/xml")
    else:
        return Response(content="<Response><Say>No input detected.</Say></Response>", media_type="application/xml")


def generate_response(user_input: str) -> str:
    """Generate a dynamic response using OpenAI."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": user_input}]
        )
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Error generating response: {e}")
        return "I'm sorry, I didn't understand that."


def synthesize_speech(text: str) -> str:
    """Convert text to speech using Google Text-to-Speech."""
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    )
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
    response = tts_client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    file_name = f"{text[:10].replace(' ', '_')}.mp3"
    with open(file_name, "wb") as out:
        out.write(response.audio_content)
    return f"https://your-server-url/{file_name}"
