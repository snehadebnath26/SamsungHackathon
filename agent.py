import os
from crewai import LLM, Agent
from tools import search_tool, transcribe_audio, equipment_identifier

# Set up Gemini LLM
gemini_api_key = os.getenv("GEMINI_API_KEY")
gemini_llm = LLM(
    model='gemini/gemini-1.5-flash',
    api_key=gemini_api_key,
    temperature=0.2
)

# Agent: Document Searcher
doc_agent = Agent(
    role="Document Searcher",
    goal="To find the most optimum solution for a given query.",
    backstory="You are a research assistant skilled at searching PDFs and extracting the most relevant information and formating in a structed manner",
    llm=gemini_llm,
    tools=[search_tool],
    verbose=True
)

# Agent: Voice Transcriber
voice_transcriber_agent = Agent(
    role="Voice Transcriber",
    goal="Return only the exact text transcription of the audio file {audio}. Do not add explanations, formatting, or commentary.",
    backstory="",
    llm=gemini_llm,
    tools=[transcribe_audio],
    verbose=True
)

# Agent: Equipment Identifier
equipment_identifier_agent = Agent(
    role="Equipment Identifier",
    goal="Identifies the equipment present in the given image {image}.",
    backstory="You are an industrial expert skilled at analyzing images to identify equipment.",
    llm=gemini_llm,
    tools=[equipment_identifier],
    verbose=True
)

