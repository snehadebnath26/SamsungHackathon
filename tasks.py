from crewai import Task
from agent import doc_agent, voice_transcriber_agent, equipment_identifier_agent

# Task: Voice Transcriber
transcribe_task = Task(
    description=(
        "Take the user input of voice path {audio} and transcribe the audio file into text."
    ),
    agent=voice_transcriber_agent,
    expected_output="Output given by `transcribe_audio` tool."
)

# Task: Equipment Identifier
equipment_identify_task = Task(
    description=(
        "Take the user input of image path {image} and identify the equipment present in the image."
    ),
    agent=equipment_identifier_agent,
    expected_output="Name of the equipment identified."
)

# Task: Document Search
search_task = Task(
    description=(
        "Take the output from `equipment_identifier_task` and `transcribe_task` and combine them "
        "and use this information to search through the .database/ folder containing PDFs. "
        "Retrieve the most relevant answer and then understand it and provide a well-structured answer in bullet points."
    ),
    agent=doc_agent,
    expected_output="A well-structured answer to the user query, based only on the PDF contents.",
    context = [equipment_identify_task, transcribe_task]
)