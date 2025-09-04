import sys
from contextlib import contextmanager
from io import StringIO
import re
from datetime import datetime

class ProcessOutput:
    def __init__(self, container=None):
        self.container = container
        self.output_text = ""
        self.seen_lines = set()
        self.agent_outputs = {}
        self.current_agent = None
        self.processing_status = "idle"
        
    def clean_text(self, text):
        # Remove ANSI escape codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        text = ansi_escape.sub('', text)
        
        # Remove LiteLLM debug messages and other noise
        noise_patterns = [
            'LiteLLM.Info:',
            'Provider List:',
            'DEBUG:',
            'INFO:',
            'WARNING:'
        ]
        
        for pattern in noise_patterns:
            if text.strip().startswith(pattern):
                return None
        
        # Clean up the formatting
        text = text.replace('[1m', '').replace('[95m', '').replace('[92m', '').replace('[00m', '')
        text = text.replace('\x1b[0m', '').replace('\x1b[1m', '').replace('\x1b[95m', '').replace('\x1b[92m', '')
        
        return text
    
    def parse_agent_info(self, text):
        """Extract agent information from the output"""
        # Patterns to identify different agents and their outputs
        agent_patterns = {
            'Equipment Identifier': r'Equipment Identifier|equipment.*identifier|identifying.*equipment',
            'Voice Transcriber': r'Voice Transcriber|transcrib|audio.*processing',
            'Document Searcher': r'Document Searcher|search.*document|searching.*pdf'
        }
        
        text_lower = text.lower()
        
        # Check if this line indicates a specific agent is working
        for agent_name, pattern in agent_patterns.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                self.current_agent = agent_name
                if agent_name not in self.agent_outputs:
                    self.agent_outputs[agent_name] = []
                return agent_name
        
        return None
    
    def format_agent_output(self):
        """Format the agent outputs for display"""
        if not self.agent_outputs:
            return "🔄 **Initializing agents...**"
        
        formatted_output = []
        
        for agent_name, outputs in self.agent_outputs.items():
            if outputs:
                formatted_output.append(f"🤖 **{agent_name}**:")
                for output in outputs[-3:]:  # Show last 3 outputs per agent
                    formatted_output.append(f"   {output}")
                formatted_output.append("")
        
        # Add current status
        if self.processing_status == "processing":
            if self.current_agent:
                formatted_output.append(f"⚡ **Currently Processing**: {self.current_agent}")
            else:
                formatted_output.append("⚡ **Processing...**")
        
        return "\n".join(formatted_output) if formatted_output else "🔄 **Starting analysis...**"
        
    def write(self, text):
        cleaned_text = self.clean_text(text)
        if cleaned_text is None:
            return
        
        # Parse agent information
        agent_detected = self.parse_agent_info(cleaned_text)
        
        # Split into lines and process each line
        lines = cleaned_text.split('\n')
        new_lines = []
        
        for line in lines:
            line = line.strip()
            if line and line not in self.seen_lines:
                self.seen_lines.add(line)
                
                # Add to current agent's output if we have one
                if self.current_agent and line:
                    if self.current_agent not in self.agent_outputs:
                        self.agent_outputs[self.current_agent] = []
                    self.agent_outputs[self.current_agent].append(line)
                
                new_lines.append(line)
        
        if new_lines or agent_detected:
            # Update the display with formatted agent output only if container exists
            if self.container:
                formatted_output = self.format_agent_output()
                self.container.markdown(formatted_output)
    
    def set_processing_status(self, status):
        """Update processing status"""
        self.processing_status = status
        if status == "completed":
            self.current_agent = None
        
        # Update display only if container exists
        if self.container:
            formatted_output = self.format_agent_output()
            self.container.markdown(formatted_output)
    
    def add_agent_output(self, agent_name, output):
        """Manually add agent output"""
        if agent_name not in self.agent_outputs:
            self.agent_outputs[agent_name] = []
        self.agent_outputs[agent_name].append(output)
        
        # Update display only if container exists
        if self.container:
            formatted_output = self.format_agent_output()
            self.container.markdown(formatted_output)
        
    def flush(self):
        pass

# Enhanced context manager for better agent output capture
@contextmanager
def capture_agent_output(container):
    """Capture stdout and redirect it to a Streamlit container with agent parsing."""
    output_handler = ProcessOutput(container)
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    
    # Redirect both stdout and stderr
    sys.stdout = output_handler
    sys.stderr = output_handler
    
    try:
        yield output_handler
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

@contextmanager
def capture_output(container):
    """Capture stdout and redirect it to a Streamlit container."""
    string_io = StringIO()
    output_handler = ProcessOutput(container)
    old_stdout = sys.stdout
    sys.stdout = output_handler
    try:
        yield string_io
    finally:
        sys.stdout = old_stdout

# Real-time agent monitoring class
class AgentMonitor:
    """Monitor and display agent progress in real-time"""
    
    def __init__(self, container):
        self.container = container
        self.agents_status = {
            'Equipment Identifier': {'status': 'waiting', 'output': [], 'start_time': None},
            'Voice Transcriber': {'status': 'waiting', 'output': [], 'start_time': None},
            'Document Searcher': {'status': 'waiting', 'output': [], 'start_time': None}
        }
        self.current_step = 0
        self.total_steps = 3
    
    def start_agent(self, agent_name):
        """Mark an agent as started"""
        if agent_name in self.agents_status:
            self.agents_status[agent_name]['status'] = 'running'
            self.agents_status[agent_name]['start_time'] = datetime.now()
            self.update_display()
    
    def complete_agent(self, agent_name, output):
        """Mark an agent as completed with output"""
        if agent_name in self.agents_status:
            self.agents_status[agent_name]['status'] = 'completed'
            self.agents_status[agent_name]['output'].append(output)
            self.current_step += 1
            self.update_display()
    
    def add_agent_progress(self, agent_name, progress_text):
        """Add progress text for an agent"""
        if agent_name in self.agents_status:
            self.agents_status[agent_name]['output'].append(progress_text)
            self.update_display()
    
    def update_display(self):
        """Update the display with current agent status"""
        display_text = []
        
        # Progress bar
        progress = self.current_step / self.total_steps
        progress_bar = "▓" * int(progress * 20) + "░" * (20 - int(progress * 20))
        display_text.append(f"**Progress**: [{progress_bar}] {self.current_step}/{self.total_steps} agents completed\n")
        
        # Agent status
        status_icons = {'waiting': '⏳', 'running': '🔄', 'completed': '✅'}
        
        for agent_name, info in self.agents_status.items():
            icon = status_icons.get(info['status'], '❓')
            status_text = info['status'].upper()
            
            display_text.append(f"{icon} **{agent_name}**: {status_text}")
            
            # Show recent outputs
            if info['output']:
                for output in info['output'][-2:]:  # Show last 2 outputs
                    display_text.append(f"   └─ {output}")
            
            # Show elapsed time for running agents
            if info['status'] == 'running' and info['start_time']:
                elapsed = (datetime.now() - info['start_time']).total_seconds()
                display_text.append(f"   └─ Running for {elapsed:.1f}s")
            
            display_text.append("")
        
        if self.container:
            self.container.markdown("\n".join(display_text))

# Export functions
__all__ = ['capture_output', 'capture_agent_output', 'AgentMonitor']