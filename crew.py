from crewai import Crew, Process
from agent import doc_agent, voice_transcriber_agent, equipment_identifier_agent
from tasks import search_task, transcribe_task, equipment_identify_task

crew = Crew(
    agents=[equipment_identifier_agent, voice_transcriber_agent, doc_agent],
    tasks=[equipment_identify_task, transcribe_task, search_task],
    process=Process.sequential,  
    verbose=True
)

# Example run
if __name__ == "__main__":
    image = "uploaded_image/image.jpg"
    audio = "uploaded_audio/livestream.wav"
    result = crew.kickoff(inputs={"image": image, "audio": audio})
    print("\n--- Final Answer ---\n", result)
