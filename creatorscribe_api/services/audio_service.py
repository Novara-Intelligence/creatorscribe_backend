"""
Audio service for video to audio conversion using ffmpeg
"""
import os
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class AudioService:
    """Service class for video to audio conversion"""
    
    @staticmethod
    def video_to_audio(
        video_path: str,
        output_path: Optional[str] = None,
        audio_format: str = 'mp3',
        audio_bitrate: str = '192k'
    ) -> Tuple[bool, str]:
        """
        Convert video to audio using ffmpeg
        
        Args:
            video_path: Path to input video file
            output_path: Path to output audio file (optional, will auto-generate if None)
            audio_format: Output audio format (default: mp3)
            audio_bitrate: Audio bitrate (default: 192k)
        
        Returns:
            Tuple[bool, str]: (Success status, output file path or error message)
        """
        try:
            # Check if video file exists
            if not os.path.exists(video_path):
                error_msg = f"Video file not found: {video_path}"
                logger.error(error_msg)
                return False, error_msg
            
            # Generate output path if not provided
            if output_path is None:
                video_name = Path(video_path).stem
                output_path = str(Path(video_path).parent / f"{video_name}.{audio_format}")
            
            # Ensure output directory exists
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Build ffmpeg command
            command = [
                'ffmpeg',
                '-i', video_path,           # Input video
                '-vn',                       # Disable video
                '-acodec', 'libmp3lame',     # Audio codec
                '-ab', audio_bitrate,        # Audio bitrate
                '-ar', '44100',              # Sample rate
                '-y',                        # Overwrite output
                output_path                  # Output audio
            ]
            
            logger.info(f"Converting video to audio: {video_path} -> {output_path}")
            
            # Execute ffmpeg
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                logger.info(f"Conversion successful: {output_path} ({file_size} bytes)")
                return True, output_path
            else:
                error_msg = f"Conversion failed: {result.stderr}"
                logger.error(error_msg)
                return False, error_msg
        
        except subprocess.TimeoutExpired:
            error_msg = "Conversion timeout (>5 minutes)"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Conversion failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    