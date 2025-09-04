import streamlit as st
import os
from datetime import datetime
from api import process_inputs_sync, ResponseFormatter
from config import (
    APP_TITLE, APP_ICON, UPLOADED_IMAGE_DIR, UPLOADED_AUDIO_DIR, 
    AUDIO_FILENAME, ALLOWED_IMAGE_TYPES, CONTAINER_HEIGHT, 
    IMAGE_DISPLAY_WIDTH, validate_environment, ensure_directories
)
from utils import SessionUtils, ValidationUtils

st.set_page_config(
    page_title=APP_TITLE, 
    layout="wide",
    initial_sidebar_state="collapsed",
    page_icon=APP_ICON
)

# Validate environment on startup
try:
    validate_environment()
    ensure_directories()
except Exception as e:
    st.error(f"Configuration Error: {e}")
    st.stop()

class SessionManager:
    """Manages session state and file cleanup"""

    IMAGE_UPLOADER_KEY_BASE = "image_uploader"
    AUDIO_RECORDER_KEY_BASE = "audio_recorder"

    @staticmethod
    def clear_directories():
        """Clear all files from upload directories"""
        for directory in (UPLOADED_IMAGE_DIR, UPLOADED_AUDIO_DIR):
            if directory.exists():
                for p in directory.iterdir():
                    if p.is_file():
                        try:
                            p.unlink()
                        except Exception as e:
                            st.error(f"Error deleting {p}: {e}")
            else:
                directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def reset_session():
        """Reset session state and clear files, including uploader widgets"""
        SessionManager.clear_directories()

        # Remove stored file paths explicitly
        st.session_state.pop("uploaded_image_path", None)
        st.session_state.pop("uploaded_audio_path", None)
        st.session_state.pop("agent_responses", None)
        st.session_state.pop("conversation_history", None)
        st.session_state.pop("processing", None)

        # Bump widget keys so Streamlit re-renders blank inputs
        st.session_state["_image_uploader_key_version"] = st.session_state.get("_image_uploader_key_version", 0) + 1
        st.session_state["_audio_recorder_key_version"] = st.session_state.get("_audio_recorder_key_version", 0) + 1

        SessionManager.initialize_session_state()

    @staticmethod
    def initialize_session_state():
        """Initialize session state variables"""
        defaults = {
            "agent_responses": [],
            "conversation_history": [],
            "processing": False,
            "uploaded_image_path": None,
            "uploaded_audio_path": None,
            "session_start_time": datetime.now().isoformat(),
            "_image_uploader_key_version": 0,
            "_audio_recorder_key_version": 0,
        }
        for k, v in defaults.items():
            st.session_state.setdefault(k, v)
        SessionUtils.log_session_activity("session_initialized")

class FileManager:
    """Manages file operations"""
    
    @staticmethod
    def save_uploaded_file(uploaded_file, upload_dir):
        """Save uploaded file to directory and return file path"""
        try:
            # Validate file type
            validation = ValidationUtils.validate_image_file(uploaded_file)
            
            if not validation["is_valid"]:
                raise ValueError(validation["error"])
            
            # Generate filename
            file_extension = uploaded_file.name.split('.')[-1].lower()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"image.{file_extension}"  # Simple name with extension
            
            # Ensure directory exists
            os.makedirs(str(upload_dir), exist_ok=True)
            
            # Create file path
            file_path = str(upload_dir / filename)
            
            # Save file
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Log activity
            SessionUtils.log_session_activity("image_uploaded", {
                "filename": filename,
                "size": validation["file_info"]["size_formatted"]
            })
            
            return file_path
            
        except Exception as e:
            # Log upload error
            SessionUtils.log_session_activity("image_upload_failed", {
                "filename": uploaded_file.name if uploaded_file else "unknown",
                "error": str(e)
            })
            raise

    @staticmethod  
    def save_uploaded_image(uploaded_image):
        """Save uploaded image and return file path"""
        return FileManager.save_uploaded_file(uploaded_image, UPLOADED_IMAGE_DIR)

    @staticmethod
    def save_uploaded_audio(uploaded_audio):
        """Save uploaded audio to the designated directory"""
        if uploaded_audio is not None:
            # Validate file first
            validation = ValidationUtils.validate_audio_file(uploaded_audio)
            if not validation["is_valid"]:
                for error in validation["errors"]:
                    st.error(f"Audio validation error: {error}")
                return None
            
            # Show warnings if any
            for warning in validation["warnings"]:
                st.warning(f"Audio warning: {warning}")
            
            # Create directory if it doesn't exist
            os.makedirs(str(UPLOADED_AUDIO_DIR), exist_ok=True)
            # Use timestamped filename to avoid stale reads
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            base_ext = AUDIO_FILENAME.split('.')[-1]
            dynamic_filename = f"audio_{timestamp}.{base_ext}"
            file_path = str(UPLOADED_AUDIO_DIR / dynamic_filename)
            
            # Save audio file
            with open(file_path, "wb") as f:
                f.write(uploaded_audio.getbuffer())
            
            # Log activity
            SessionUtils.log_session_activity("audio_recorded", {
                "filename": dynamic_filename,
                "size": validation["file_info"]["size_formatted"]
            })
            
            return file_path
        return None
    
    @staticmethod
    def delete_file(file_path):
        """Delete a specific file"""
        if file_path and os.path.exists(file_path):
            try:
                os.unlink(file_path)
                SessionUtils.log_session_activity("file_deleted", {"file_path": file_path})
                return True
            except Exception as e:
                st.error(f"Error deleting file {file_path}: {e}")
                return False
        return False

class AgentManager:
    """Manages agent interactions"""
    
    @staticmethod
    def process_inputs(image_path, audio_path, monitor_container=None):
        """Process inputs through the crew agent network"""
        try:
            # Use the API module for processing with monitoring
            result_data = process_inputs_sync(image_path, audio_path, monitor_container)
            return result_data
        except Exception as e:
            if monitor_container:
                monitor_container.error(f"Error processing inputs with agents: {e}")
            else:
                st.error(f"Error processing inputs with agents: {e}")
            return None
    
    @staticmethod
    def run_agent_processing(image_path, audio_path):
        """Run agent processing synchronously to avoid ScriptRunContext warnings"""
        # Log start
        SessionUtils.log_session_activity("query_processing_started", {"image_path": image_path, "audio_path": audio_path})
        result_data = AgentManager.process_inputs(image_path, audio_path, None)
        if result_data and result_data.get("status") == "success":
            formatted_responses = ResponseFormatter.format_for_streamlit(result_data)
            st.session_state.agent_responses = formatted_responses
            st.session_state.conversation_history.append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "image_path": image_path,
                "audio_path": audio_path,
                "response": formatted_responses,
                "raw_result": result_data
            })
            SessionUtils.log_session_activity("query_processed", {"status": "success", "response_count": len(formatted_responses)})
        else:
            error_msg = (result_data or {}).get("error", "Unknown error occurred")
            st.session_state.agent_responses = [f"❌ Error processing your request: {error_msg}"]
            SessionUtils.log_session_activity("query_processing_failed", {"error": error_msg})


def main():
    """Main application function"""
    
    # Initialize session state
    SessionManager.initialize_session_state()
    
    # Clear directories on first run or manual trigger
    if "initialized" not in st.session_state:
        SessionManager.clear_directories()
        st.session_state.initialized = True
    
    # Sidebar removed as per user request
    
    # Title bar with new session button
    col_title, col_btn = st.columns([5, 1])
    with col_title:
        st.markdown(
            f"<h2 style='text-align: left; color: #1f77b4;'>{APP_ICON} {APP_TITLE}</h2>", 
            unsafe_allow_html=True
        )
    with col_btn:
        if st.button("🔄 New Session", help="Start a new session and clear all data", key="new_session_btn"):
            SessionManager.reset_session()
            st.rerun()
    
    # Main layout
    col1, col2 = st.columns([1, 1])
    
    # Left column - Input panel
    with col1:
        with st.container(height=CONTAINER_HEIGHT):
            st.markdown("### 📥 Input Panel")
            
            # Image input section
            st.markdown("#### Equipment Image")
            img_widget_key = f"image_uploader_{st.session_state._image_uploader_key_version}"
            uploaded_image = st.file_uploader(
                "Upload Equipment Image",
                type=ALLOWED_IMAGE_TYPES,
                key=img_widget_key,
                help="Upload an image of the equipment you need help with"
            )
            
            # Handle image upload
            current_image_path = st.session_state.get("uploaded_image_path")
            
            if uploaded_image is not None:
                # Save new image
                new_image_path = FileManager.save_uploaded_image(uploaded_image)
                
                # Delete old image if different
                if current_image_path and current_image_path != new_image_path:
                    FileManager.delete_file(current_image_path)
                
                st.session_state.uploaded_image_path = new_image_path
                
                # Display image with remove button
                img_col, btn_col = st.columns([10, 1])
                with img_col:
                    st.image(
                        uploaded_image,
                        caption="Uploaded Equipment Image",
                        use_container_width=False,
                        width=IMAGE_DISPLAY_WIDTH
                    )
                with btn_col:
                    if st.button("❌", help="Remove image", key=f"remove_img_{st.session_state._image_uploader_key_version}"):
                        # Delete file on disk
                        FileManager.delete_file(st.session_state.uploaded_image_path)
                        # Force widget reset by bumping version
                        st.session_state._image_uploader_key_version += 1
                        st.session_state.uploaded_image_path = None
                        st.rerun()
            
            elif current_image_path:
                # Display existing image
                if os.path.exists(current_image_path):
                    img_col, btn_col = st.columns([10, 1])
                    with img_col:
                        st.image(
                            current_image_path,
                            caption="Current Equipment Image",
                            use_container_width=False,
                            width=IMAGE_DISPLAY_WIDTH
                        )
                    with btn_col:
                        if st.button("❌", help="Remove image", key=f"remove_img_existing_{st.session_state._image_uploader_key_version}"):
                            FileManager.delete_file(st.session_state.uploaded_image_path)
                            st.session_state._image_uploader_key_version += 1
                            st.session_state.uploaded_image_path = None
                            st.rerun()
                else:
                    # File was deleted externally
                    st.session_state.uploaded_image_path = None
            
            else:
                # No image placeholder
                st.markdown(
                    """
                    <div style="width:100%;height:200px;border:2px dashed #cccccc;
                    display:flex;align-items:center;justify-content:center;
                    border-radius:10px;color:#888888;font-size:16px;
                    background-color:#f8f9fa;">
                    📷 Upload Equipment Image
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            
            st.markdown("---")
            
            # Audio input section
            st.markdown("#### 🎤 Voice Query")
            audio_widget_key = f"audio_recorder_{st.session_state._audio_recorder_key_version}"
            audio_input = st.audio_input(
                "Record your query about the equipment",
                help="Record your voice query describing the issue or question",
                key=audio_widget_key
            )
            
            # Handle audio upload
            current_audio_path = st.session_state.get("uploaded_audio_path")
            
            if audio_input is not None:
                new_audio_path = FileManager.save_uploaded_audio(audio_input)
                if current_audio_path and current_audio_path != new_audio_path:
                    FileManager.delete_file(current_audio_path)
                st.session_state.uploaded_audio_path = new_audio_path
                # Invalidate previous agent responses to avoid stale output usage
                st.session_state.agent_responses = []
                st.success("✅ Audio recorded successfully!")
                
               
            
            elif current_audio_path and os.path.exists(current_audio_path):
                st.success("✅ Audio file ready")
               
            
            # Status and action section
            st.markdown("---")
            st.markdown("#### ✨ Action")
            
            # Check input status and provide guidance
            has_image = st.session_state.uploaded_image_path is not None
            has_audio = st.session_state.uploaded_audio_path is not None
            
            if not has_image and not has_audio:
                st.info("📝 Please upload an equipment image and record your voice query to get started.")
            elif not has_image and has_audio:
                st.warning("⚠️ Please upload an image of your equipment first.")
            elif has_image and not has_audio:
                st.info("🎙️ Great! Now you can record your voice query about the equipment.")
            else:
                # Both inputs are available
                if st.button("🔍 Analyze Equipment", type="primary"):
                    st.session_state.processing = True
                    st.session_state.start_analysis = True
                    st.session_state.agent_responses = []
    
    # Right column - Conversation panel
    with col2:
        with st.container(height=CONTAINER_HEIGHT):
            st.markdown("### 💬 Agent Response")
            
            # Show real-time monitoring during processing
            if st.session_state.processing and 'monitor_container' in st.session_state:
                st.markdown("#### 🔍 Real-time Analysis")
                # The monitor container will be updated by the processing thread
                st.session_state.monitor_container.empty()
                st.markdown("---")
            
            # Trigger processing inline with placeholder if start_analysis is set
            if st.session_state.get("start_analysis") and st.session_state.get("processing"):
                placeholder = st.empty()
                analyzing_html = """
                <div style='display:flex;align-items:center;justify-content:center;height:250px;'>
                    <div style='text-align:center;'>
                        <div style='font-size:20px;font-weight:600;'>🔍 Analysing the query ...</div>
                        <div style='margin-top:12px;font-size:14px;color:#666;'>This may take a moment while agents process your image and audio.</div>
                        <div style='margin-top:18px;'>
                            <span class='loader'></span>
                        </div>
                    </div>
                </div>
                <style>
                .loader {width:56px;height:56px;border-radius:50%;display:inline-block;border-top:4px solid #1f77b4;border-right:4px solid transparent;box-sizing:border-box;animation:rotation 1s linear infinite;}
                @keyframes rotation {0% {transform: rotate(0deg);}100% {transform: rotate(360deg);}}
                </style>
                """
                with placeholder.container():
                    with st.chat_message("assistant", avatar="🤖"):
                        st.markdown(analyzing_html, unsafe_allow_html=True)
                # Run processing
                AgentManager.run_agent_processing(
                    st.session_state.uploaded_image_path,
                    st.session_state.uploaded_audio_path
                )
                # Remove analyzing placeholder before showing results
                try:
                    placeholder.empty()
                except Exception:
                    pass
                st.session_state.processing = False
                st.session_state.start_analysis = False
            # Display agent responses
            if st.session_state.agent_responses and not st.session_state.get("processing"):
                st.markdown("#### 🤖 Agent Analysis")
                
                # Create chat-style responses
                for i, response in enumerate(st.session_state.agent_responses):
                    with st.chat_message("assistant", avatar="🤖"):
                        if isinstance(response, str):
                            st.markdown(response)
                        else:
                            st.write(response)
                
                # Add download option for results
                if len(st.session_state.agent_responses) > 1:
                    st.markdown("---")
                    result_text = "\n\n".join([
                        str(resp) for resp in st.session_state.agent_responses
                    ])
                    st.download_button(
                        label="📥 Download Analysis Results",
                        data=result_text,
                        file_name=f"aura_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain"
                    )
            
            elif st.session_state.get("processing"):
                # Processing but no start_analysis flag (edge case) show generic message
                st.markdown("#### 🤖 Agent Analysis")
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown("🔄 Processing...")
            
            else:
                # Welcome message
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown("""
                    **Welcome to Aura! 🎉**
                    
                    I'm your Enterprise Operations Assistant, ready to help you with equipment-related queries.
                    
                    **How to get started:**
                    1. 📷 Upload an image of your equipment
                    2. 🎤 Record your voice query describing the issue
                    3. 🔍 Click 'Analyze Equipment' to get assistance
                    
                    I'll analyze your equipment and provide detailed solutions based on our knowledge base!
                    
                    **What happens during analysis:**
                    - 🔎 **Equipment Identifier** analyzes your image
                    - 🎙️ **Voice Transcriber** processes your audio query  
                    - 📚 **Document Searcher** finds relevant solutions
                    """)
            
            # Show the monitor container if it exists during processing
            if st.session_state.processing and 'monitor_container' in st.session_state:
                st.session_state.monitor_container = st.empty()


if __name__ == "__main__":
    main()
