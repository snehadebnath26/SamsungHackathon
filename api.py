import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import traceback

from crew import crew
from agent import doc_agent, voice_transcriber_agent, equipment_identifier_agent
from tasks import search_task, transcribe_task, equipment_identify_task
from output_handler import capture_agent_output, AgentMonitor

class AgentAPI:
    """API class for handling agent interactions"""
    
    def __init__(self):
        self.processing_status = {}
    
    async def process_request(self, image_path: str, audio_path: str, monitor_container=None) -> Dict[str, Any]:
        """
        Process image and audio inputs through the agent crew
        
        Args:
            image_path (str): Path to the uploaded image
            audio_path (str): Path to the uploaded audio
            monitor_container: Streamlit container for real-time monitoring
            
        Returns:
            Dict containing processed results and individual agent outputs
        """
        request_id = f"req_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Mark as processing
            self.processing_status[request_id] = {
                "status": "processing",
                "start_time": datetime.now(),
                "current_task": "initializing"
            }
            
            # Validate inputs
            if not Path(image_path).exists():
                raise FileNotFoundError(f"Image file not found: {image_path}")
            if not Path(audio_path).exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
            # Setup monitoring if container is provided
            monitor = None
            if monitor_container:
                monitor = AgentMonitor(monitor_container)
                monitor.add_agent_progress("System", "🚀 Starting agent analysis...")
            
            # Update status
            self.processing_status[request_id]["current_task"] = "running_agents"
            
            # Run the crew with monitoring
            inputs = {
                "image": image_path,
                "audio": audio_path
            }
            
            # Capture agent outputs during processing
            if monitor_container:
                with capture_agent_output(monitor_container) as output_handler:
                    if monitor:
                        monitor.start_agent("Equipment Identifier")
                    
                    result = crew.kickoff(inputs=inputs)
                    
                    if monitor:
                        monitor.complete_agent("Equipment Identifier", "Equipment analysis completed")
                        monitor.complete_agent("Voice Transcriber", "Audio transcription completed") 
                        monitor.complete_agent("Document Searcher", "Document search completed")
            else:
                result = crew.kickoff(inputs=inputs)
            
            # Extract individual task outputs
            formatted_result = self._format_crew_result(result)
            
            # Update status
            self.processing_status[request_id].update({
                "status": "completed",
                "end_time": datetime.now(),
                "result": formatted_result
            })
            
            return {
                "request_id": request_id,
                "status": "success",
                "data": formatted_result,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            # Update status with error
            self.processing_status[request_id] = {
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "timestamp": datetime.now().isoformat()
            }
            
            if monitor_container:
                monitor_container.error(f"❌ **Error**: {str(e)}")
            
            return {
                "request_id": request_id,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _format_crew_result(self, result) -> Dict[str, Any]:
        """
        Format the crew result for frontend consumption
        
        Args:
            result: Result from crew.kickoff()
            
        Returns:
            Formatted result dictionary
        """
        formatted_result = {
            "final_answer": "",
            "agent_outputs": {},
            "task_outputs": [],
            "execution_time": None
        }
        
        try:
            # Extract final answer
            if hasattr(result, 'raw'):
                formatted_result["final_answer"] = str(result.raw)
            else:
                formatted_result["final_answer"] = str(result)
            
            # Extract individual task outputs if available
            if hasattr(result, 'tasks_output') and result.tasks_output:
                for i, task_output in enumerate(result.tasks_output):
                    # Extract agent name robustly (Agent object -> its role if present)
                    raw_agent = getattr(task_output, 'agent', 'Unknown Agent')
                    agent_name = getattr(raw_agent, 'role', None) or getattr(raw_agent, 'name', None) or str(raw_agent)

                    # Helper to extract primary textual content
                    def extract_primary(o):
                        for attr in ['output', 'result', 'raw_output', 'raw', 'final_answer', 'content']:
                            if hasattr(o, attr):
                                val = getattr(o, attr)
                                if isinstance(val, (str, list)) and val:
                                    if isinstance(val, list):
                                        return "\n".join(map(str, val))
                                    return str(val)
                        return str(o)

                    content_text = extract_primary(task_output).strip()

                    # Extract tool outputs if available
                    tool_outputs_text = ""
                    try:
                        possible_attrs = ['tool_outputs', 'tools_output', 'tool_results']
                        for attr in possible_attrs:
                            if hasattr(task_output, attr):
                                val = getattr(task_output, attr)
                                if isinstance(val, (list, tuple)) and val:
                                    collected = []
                                    for item in val:
                                        if isinstance(item, dict):
                                            # Common keys: 'output', 'content', 'result'
                                            for k in ['output', 'content', 'result', 'text']:
                                                if k in item and item[k]:
                                                    collected.append(str(item[k]))
                                                    break
                                        else:
                                            collected.append(str(item))
                                    if collected:
                                        tool_outputs_text = "\n".join(collected)
                                        break
                    except Exception:
                        pass

                    # If main content appears empty but we have tool outputs, use them
                    if (not content_text or content_text == '```') and tool_outputs_text:
                        content_text = tool_outputs_text.strip()

                    # If content wrapped in backticks, extract inner block
                    if '```' in content_text:
                        parts = content_text.split('```')
                        # choose first non-empty trimmed between fences
                        inner = None
                        for seg in parts[1:]:
                            seg = seg.strip('\n')
                            if seg and not seg.startswith(('python', 'txt')):
                                inner = seg
                                break
                        if inner:
                            content_text = inner.strip()

                    task_info = {
                        "task_index": i,
                        "task_name": getattr(task_output, 'name', f'Task {i+1}'),
                        "agent_name": agent_name,
                        "output": content_text,
                        "raw_str": str(task_output),
                        "tool_outputs": tool_outputs_text or None,
                        "execution_time": getattr(task_output, 'execution_time', None)
                    }
                    formatted_result["task_outputs"].append(task_info)

                    if agent_name not in formatted_result["agent_outputs"]:
                        formatted_result["agent_outputs"][agent_name] = []
                    formatted_result["agent_outputs"][agent_name].append(content_text)
            
            # Calculate total execution time if available
            if formatted_result["task_outputs"]:
                total_time = sum(
                    task.get("execution_time", 0) or 0 
                    for task in formatted_result["task_outputs"]
                )
                if total_time > 0:
                    formatted_result["execution_time"] = total_time
            
        except Exception as e:
            # If formatting fails, provide basic result
            formatted_result = {
                "final_answer": str(result),
                "agent_outputs": {},
                "task_outputs": [],
                "execution_time": None,
                "formatting_error": str(e)
            }
        
        return formatted_result
    
    def get_processing_status(self, request_id: str) -> Dict[str, Any]:
        """
        Get the current processing status of a request
        
        Args:
            request_id (str): Request identifier
            
        Returns:
            Status dictionary
        """
        return self.processing_status.get(request_id, {
            "status": "not_found",
            "error": f"Request {request_id} not found"
        })
    
    def get_agent_info(self) -> Dict[str, Any]:
        """
        Get information about available agents
        
        Returns:
            Agent information dictionary
        """
        return {
            "agents": [
                {
                    "name": "Equipment Identifier",
                    "role": equipment_identifier_agent.role,
                    "goal": equipment_identifier_agent.goal,
                    "backstory": equipment_identifier_agent.backstory
                },
                {
                    "name": "Voice Transcriber",
                    "role": voice_transcriber_agent.role,
                    "goal": voice_transcriber_agent.goal,
                    "backstory": voice_transcriber_agent.backstory
                },
                {
                    "name": "Document Searcher",
                    "role": doc_agent.role,
                    "goal": doc_agent.goal,
                    "backstory": doc_agent.backstory
                }
            ],
            "tasks": [
                {
                    "name": "Equipment Identification",
                    "description": equipment_identify_task.description,
                    "expected_output": equipment_identify_task.expected_output
                },
                {
                    "name": "Audio Transcription",
                    "description": transcribe_task.description,
                    "expected_output": transcribe_task.expected_output
                },
                {
                    "name": "Document Search",
                    "description": search_task.description,
                    "expected_output": search_task.expected_output
                }
            ]
        }

# Global API instance
agent_api = AgentAPI()

def process_inputs_sync(image_path: str, audio_path: str, monitor_container=None) -> Dict[str, Any]:
    """
    Synchronous wrapper for processing inputs
    
    Args:
        image_path (str): Path to the uploaded image
        audio_path (str): Path to the uploaded audio
        monitor_container: Streamlit container for real-time monitoring
        
    Returns:
        Processing result dictionary
    """
    return asyncio.run(agent_api.process_request(image_path, audio_path, monitor_container))

def get_status(request_id: str) -> Dict[str, Any]:
    """
    Get processing status for a request
    
    Args:
        request_id (str): Request identifier
        
    Returns:
        Status dictionary
    """
    return agent_api.get_processing_status(request_id)

def get_agents_info() -> Dict[str, Any]:
    """
    Get information about available agents and tasks
    
    Returns:
        Agent and task information
    """
    return agent_api.get_agent_info()

# Response formatting utilities
class ResponseFormatter:
    """Utility class for formatting agent responses for the frontend"""
    
    @staticmethod
    def format_for_streamlit(result_data: Dict[str, Any]) -> List[str]:
        """
        Format agent result for Streamlit display with simple terminal-like output
        
        Args:
            result_data: Result data from agent processing
            
        Returns:
            List of formatted strings for display
        """
        formatted_responses = []
        
        try:
            if result_data.get("status") == "error":
                formatted_responses.append(f"❌ **Error**: {result_data.get('error', 'Unknown error')}")
                return formatted_responses
            
            data = result_data.get("data", {})
            
            # Extract key information from task outputs
            equipment_name = "Unknown Equipment"
            issue_description = "No issue specified"
            solution = "No solution found"
            
            task_outputs = data.get("task_outputs", [])

            for task in task_outputs:
                agent_name = task.get("agent_name", "")
                output = (task.get("output") or "").strip()
                tool_outputs = (task.get("tool_outputs") or "").strip()

                # Prefer tool_outputs if main output empty
                primary = output if output and output.lower() not in {"none", "null", ""} else tool_outputs
                if not primary:
                    primary = task.get("raw_str", "").strip()

                if "Equipment Identifier" in agent_name and primary:
                    equipment_name = primary.split('\n')[0].strip()
                elif "Voice Transcriber" in agent_name and primary:
                    issue_description = primary
                elif "Document Searcher" in agent_name and primary:
                    solution = primary
            
            # Format the terminal-style output
            formatted_responses.append("🔍 **Analysis Complete!**\n")
            formatted_responses.append(f"**Equipment:** {equipment_name}")
            formatted_responses.append(f"**Issue:** {issue_description}")
            formatted_responses.append(f"**Solution:** {solution}")
            
            # Add a simplified terminal output for debugging
            terminal_output = f"""
Terminal Output:
================
Equipment: {equipment_name}
Issue: {issue_description}
Solution: {solution}
================
"""
            print(terminal_output)
            
        except Exception as e:
            formatted_responses.append(f"❌ **Formatting Error**: {str(e)}")
            print(f"Terminal Output Error: {str(e)}")
        
        return formatted_responses if formatted_responses else ["No response generated"]
    
    @staticmethod
    def format_agent_summary(result_data: Dict[str, Any]) -> str:
        """
        Create a summary of agent processing
        
        Args:
            result_data: Result data from agent processing
            
        Returns:
            Summary string
        """
        if result_data.get("status") == "error":
            return f"Processing failed: {result_data.get('error', 'Unknown error')}"
        
        data = result_data.get("data", {})
        task_count = len(data.get("task_outputs", []))
        execution_time = data.get("execution_time", 0)
        
        summary = f"Successfully processed {task_count} tasks"
        if execution_time:
            summary += f" in {execution_time:.2f} seconds"
        
        return summary
