import google.genai as genai
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(project = os.getenv('GOOGLE_APPLICATION_CREDENTIALS'))

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="Explain black holes in 2 sentences."
)

print(response.text)