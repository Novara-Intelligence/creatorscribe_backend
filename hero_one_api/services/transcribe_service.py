import os
import logging
import base64
from typing import Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

class TranscribeService:
    # Style templates with hook styles
    STYLE_TEMPLATES = {
        'professional': {
            'name': 'Professional Business',
            'prompt_modifier': 'Write in a professional, corporate tone. Use formal language, focus on business value, and maintain a polished, executive-level communication style.',
            'caption_style': 'Professional and authoritative with industry-relevant terminology',
            'description_style': 'Detailed business analysis with key insights and actionable takeaways',
            'hook_style': 'Authority-based hook that establishes credibility and business value'
        },
        'casual': {
            'name': 'Casual & Friendly', 
            'prompt_modifier': 'Write in a casual, conversational tone. Use everyday language, be relatable and approachable, like talking to a friend.',
            'caption_style': 'Friendly and conversational with emojis and casual language',
            'description_style': 'Easy-to-read explanation in a warm, personal tone',
            'hook_style': 'Relatable hook that feels like a conversation with a friend'
        },
        'educational': {
            'name': 'Educational & Informative',
            'prompt_modifier': 'Write in an educational, teaching tone. Break down complex concepts, provide clear explanations, and focus on learning outcomes.',
            'caption_style': 'Clear and informative with focus on learning and knowledge sharing',
            'description_style': 'Structured educational content with key learning points and takeaways',
            'hook_style': 'Knowledge-based hook that promises learning and insights'
        },
        'entertaining': {
            'name': 'Fun & Entertaining',
            'prompt_modifier': 'Write in a fun, energetic, and entertaining tone. Use humor, excitement, and engaging language to capture attention and entertain the audience.',
            'caption_style': 'Exciting and fun with humor, energy, and entertainment value',
            'description_style': 'Engaging narrative that entertains while informing',
            'hook_style': 'Entertainment hook with humor, surprise, or excitement to grab attention'
        },
        'inspirational': {
            'name': 'Motivational & Inspiring',
            'prompt_modifier': 'Write in an inspirational, motivational tone. Focus on empowerment, positive messaging, and encouraging action. Use uplifting language.',
            'caption_style': 'Motivational and uplifting with call-to-action elements',
            'description_style': 'Inspiring content that motivates and empowers the audience',
            'hook_style': 'Inspirational hook that motivates and creates desire for transformation'
        },
        'technical': {
            'name': 'Technical & Expert',
            'prompt_modifier': 'Write in a technical, expert tone. Use industry terminology, focus on specifications, detailed analysis, and expert-level insights.',
            'caption_style': 'Technical and precise with expert terminology and insights',
            'description_style': 'Detailed technical analysis with specifications and expert perspectives',
            'hook_style': 'Expert-level hook that demonstrates technical mastery and insider knowledge'
        },
        'storytelling': {
            'name': 'Narrative & Storytelling',
            'prompt_modifier': 'Write in a storytelling tone. Create narrative flow, use story elements, emotional connections, and paint vivid pictures with words.',
            'caption_style': 'Story-driven with narrative hooks and emotional connection',
            'description_style': 'Compelling narrative that tells a complete story',
            'hook_style': 'Narrative hook that creates curiosity and emotional connection through storytelling'
        },
        'minimalist': {
            'name': 'Clean & Minimalist',
            'prompt_modifier': 'Write in a clean, minimalist tone. Be concise, direct, and to-the-point. Focus on essential information without unnecessary elaboration.',
            'caption_style': 'Clean and concise with essential information only',
            'description_style': 'Minimal but complete explanation focusing on key points',
            'hook_style': 'Direct, impactful hook that gets straight to the point without fluff'
        },
        'viral': {
            'name': 'Viral & Trending',
            'prompt_modifier': 'Write in a viral, trending style. Use current internet language, memes, trending phrases, and create content designed to be shared widely.',
            'caption_style': 'Viral-optimized with trending language and shareability focus',
            'description_style': 'Engaging content designed for maximum reach and viral potential',
            'hook_style': 'Viral hook using trending formats, curiosity gaps, and shareable elements'
        },
        'luxury': {
            'name': 'Luxury & Premium',
            'prompt_modifier': 'Write in a luxury, premium tone. Use sophisticated language, focus on exclusivity, quality, and high-end appeal.',
            'caption_style': 'Sophisticated and premium with luxury positioning',
            'description_style': 'Elegant content that emphasizes quality and exclusivity',
            'hook_style': 'Exclusive hook that creates desire through premium positioning and scarcity'
        }
    }
    
    @staticmethod
    def get_available_styles():
        """Get list of available style options"""
        return {
            style_key: {
                'name': style_data['name'],
                'description': style_data['prompt_modifier']
            }
            for style_key, style_data in TranscribeService.STYLE_TEMPLATES.items()
        }
    
    @staticmethod
    def parse_openai_response(content: str) -> dict:
        """
        Parse OpenAI response to extract caption, description, and hashtags
        
        Args:
            content: Raw OpenAI response content
            
        Returns:
            Dict with caption, description, hashtags
        """
        logger.info(f"OpenAI raw response: {content}")
        
        caption = ""
        description = ""
        hashtags = ""
        
        try:
            # More robust parsing that handles various formats
            lines = content.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                
                # Check for section headers (case insensitive)
                if line.upper().startswith('CAPTION:'):
                    current_section = 'caption'
                    # Extract content after CAPTION:
                    caption_content = line[8:].strip()  # Remove "CAPTION:"
                    if caption_content:
                        caption = caption_content
                    continue
                elif line.upper().startswith('DESCRIPTION:'):
                    current_section = 'description'
                    # Extract content after DESCRIPTION:
                    desc_content = line[12:].strip()  # Remove "DESCRIPTION:"
                    if desc_content:
                        description = desc_content
                    continue
                elif line.upper().startswith('HASHTAGS:'):
                    current_section = 'hashtags'
                    # Extract content after HASHTAGS:
                    hashtag_content = line[9:].strip()  # Remove "HASHTAGS:"
                    if hashtag_content:
                        hashtags = hashtag_content
                    continue
                
                # Add content to current section
                if current_section and line:
                    if current_section == 'caption':
                        caption = caption + " " + line if caption else line
                    elif current_section == 'description':
                        description = description + " " + line if description else line
                    elif current_section == 'hashtags':
                        hashtags = hashtags + " " + line if hashtags else line
            
            # Fallback: try old method if new method didn't work
            if not caption and not description and not hashtags:
                if "CAPTION:" in content:
                    try:
                        caption_part = content.split("CAPTION:")[1].split("DESCRIPTION:")[0].strip()
                        caption = caption_part
                    except:
                        pass
                
                if "DESCRIPTION:" in content:
                    try:
                        desc_part = content.split("DESCRIPTION:")[1].split("HASHTAGS:")[0].strip()
                        description = desc_part
                    except:
                        pass
                
                if "HASHTAGS:" in content:
                    try:
                        hashtags_part = content.split("HASHTAGS:")[1].strip()
                        hashtags = hashtags_part
                    except:
                        pass
            
            # Final fallback: use entire content as caption if nothing parsed
            if not caption and not description and not hashtags:
                caption = content.strip()
                
        except Exception as parse_error:
            logger.error(f"Parsing error: {parse_error}, using fallback")
            caption = content.strip()  # Use entire response as caption
        
        return {
            "caption": caption,
            "description": description,
            "hashtags": hashtags
        }
    
    @staticmethod
    def format_srt_timestamp(seconds: float) -> str:
        """
        Format seconds to SRT timestamp format: HH:MM:SS,mmm
        
        Args:
            seconds: Time in seconds
            
        Returns:
            SRT formatted timestamp like "00:00:05,500"
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
    
    @staticmethod
    def transcribe(audio_file_path: str, language: Optional[str] = None, translate_to_english: bool = False) -> str:
        """
        Transcribe audio/video file to text with timestamps
        
        Args:
            audio_file_path: Path to audio or video file (mp3, mp4, wav, etc.)
            language: Language code like 'en', 'es' (auto-detect if None)
            translate_to_english: If True, translates to English instead of transcribing
            
        Returns:
            Formatted transcription like "[0:00 - 0:05] -> hello world"
        """
        try:
            if not os.path.exists(audio_file_path):
                return f"Error: File not found - {audio_file_path}"
            
            # Initialize OpenAI client (uses OPENAI_API_KEY from env)
            client = OpenAI()
            
            # Choose between transcription or translation
            if translate_to_english:
                # Translation: Translates any language to English
                with open(audio_file_path, 'rb') as audio_file:
                    result = client.audio.translations.create(
                        model='whisper-1',
                        file=audio_file,
                        response_format='verbose_json'
                    )
            else:
                # Transcription: Same language as input
                with open(audio_file_path, 'rb') as audio_file:
                    params = {
                        'model': 'whisper-1',
                        'file': audio_file,
                        'response_format': 'verbose_json',
                        'timestamp_granularities': ['segment']
                    }
                    
                    if language:
                        params['language'] = language
                    
                    result = client.audio.transcriptions.create(**params)
            
            # Format output: [00:00 - 00:15] -> text
            output_lines = []
            
            if hasattr(result, 'segments') and result.segments:
                for segment in result.segments:
                    # Access segment attributes directly (not as dict)
                    start = segment.start if hasattr(segment, 'start') else segment.get('start', 0)
                    end = segment.end if hasattr(segment, 'end') else segment.get('end', 0)
                    text = segment.text.strip() if hasattr(segment, 'text') else segment.get('text', '').strip()
                    
                    # Format time as MM:SS
                    start_min = int(start // 60)
                    start_sec = int(start % 60)
                    end_min = int(end // 60)
                    end_sec = int(end % 60)
                    
                    timestamp = f"[{start_min}:{start_sec:02d} - {end_min}:{end_sec:02d}]"
                    output_lines.append(f"{timestamp} -> {text}")
            else:
                # Fallback if no segments
                output_lines.append(result.text)
            
            return "\n".join(output_lines)
            
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            return f"Error: {str(e)}"
    
    @staticmethod
    def generate_social_media_content(
        audio_file_path: str, 
        language: Optional[str] = None,
        caption_length: str = 'medium',
        description_length: str = 'medium',
        hashtag_count: int = 15,
        style: str = 'casual',
        custom_prompt: Optional[str] = None
    ) -> dict:
        """
        Generate social media content (caption, description, hashtags) from audio/video
        Always translates to English for better social media reach
        
        Args:
            audio_file_path: Path to audio or video file
            language: Language code like 'en', 'es' (auto-detect if None)
            caption_length: 'short' (1 sentence), 'medium' (2 sentences), 'long' (3 sentences)
            description_length: 'short' (1 paragraph), 'medium' (2-3 paragraphs), 'long' (4-5 paragraphs)
            hashtag_count: Number of hashtags to generate (5-30, default: 15)
            style: Writing style ('professional', 'casual', 'educational', 'viral', 'luxury', etc.)
            custom_prompt: Additional custom instructions (optional, independent of style)
            
        Returns:
            Dict with caption, description, hashtags for Instagram, Facebook, YouTube
        """
        try:
            # Always translate to English for social media content
            transcription = TranscribeService.transcribe(audio_file_path, language, translate_to_english=True)
            
            if transcription.startswith("Error:"):
                return {"error": transcription}
            
            # Initialize OpenAI client
            client = OpenAI()
            
            # Define caption length requirements
            caption_requirements = {
                'short': '1 sentence (concise and punchy)',
                'medium': '2 sentences (engaging with hook)',
                'long': '3 sentences (detailed with strong hook)'
            }
            
            # Define description length requirements
            description_requirements = {
                'short': '1 paragraph (brief overview)',
                'medium': '2-3 paragraphs (detailed explanation)',
                'long': '4-5 paragraphs (comprehensive and detailed)'
            }
            
            caption_req = caption_requirements.get(caption_length, caption_requirements['medium'])
            description_req = description_requirements.get(description_length, description_requirements['medium'])
            
            # Validate and set hashtag count
            hashtag_count = max(5, min(30, hashtag_count))  # Ensure between 5 and 30
            
            # Get style configuration
            style_config = TranscribeService.STYLE_TEMPLATES.get(style, TranscribeService.STYLE_TEMPLATES['casual'])
            
            # Prepare combined prompt instructions
            combined_instructions = style_config['prompt_modifier']
            if custom_prompt:
                combined_instructions += f" ADDITIONAL CUSTOM INSTRUCTIONS: {custom_prompt}"
            
            # Create prompt for social media content generation with style
            prompt = f"""Based on this video transcription, generate social media content for Instagram, Facebook, and YouTube:

                Transcription:
                {transcription}

                STYLE INSTRUCTIONS: {combined_instructions}

                Please provide:
                1. A caption ({caption_req}) - {style_config['caption_style']} with {style_config['hook_style']}
                2. A detailed description ({description_req}) - {style_config['description_style']}
                3. Exactly {hashtag_count} trending hashtags relevant to the content

                Format the response as:

                CAPTION:
                [Your styled caption here following the style instructions]

                DESCRIPTION:
                [Your styled description here following the style instructions]

                HASHTAGS:
                [Your hashtags separated by spaces, like: #trending #video #content]
            """
            
            # Call OpenAI API for content generation
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"You are a social media expert who creates engaging captions, descriptions, and trending hashtags for video content. You adapt your writing style based on specific instructions to match different tones and audiences. Make content suitable for Instagram, Facebook, and YouTube. Current style: {combined_instructions}"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            # Parse the response using the improved parser
            content = response.choices[0].message.content
            result = TranscribeService.parse_openai_response(content)
            
            logger.info(f"Social media content generated for: {audio_file_path}")
            return result
            
        except Exception as e:
            logger.error(f"Social media content generation failed: {str(e)}")
            return {"error": f"Error: {str(e)}"}
    
    @staticmethod
    def generate_social_media_content_from_image(
        image_file_path: str,
        caption_length: str = 'medium',
        description_length: str = 'medium',
        hashtag_count: int = 15,
        style: str = 'casual',
        custom_prompt: Optional[str] = None
    ) -> dict:
        """
        Generate social media content (caption, description, hashtags) from an image
        Uses OpenAI Vision API to analyze the image and create engaging content
        
        Args:
            image_file_path: Path to image file (jpg, png, webp, etc.)
            caption_length: 'short' (1 sentence), 'medium' (2 sentences), 'long' (3 sentences)
            description_length: 'short' (1 paragraph), 'medium' (2-3 paragraphs), 'long' (4-5 paragraphs)
            hashtag_count: Number of hashtags to generate (5-30, default: 15)
            style: Writing style ('professional', 'casual', 'educational', 'viral', 'luxury', etc.)
            custom_prompt: Additional custom instructions (optional, independent of style)
            
        Returns:
            Dict with caption, description, hashtags for Instagram, Facebook, YouTube
        """
        try:
            if not os.path.exists(image_file_path):
                return {"error": f"Error: File not found - {image_file_path}"}
            
            # Check if file is an image
            valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
            if not image_file_path.lower().endswith(valid_extensions):
                return {"error": f"Error: Invalid image format. Supported formats: {', '.join(valid_extensions)}"}
            
            # Read and encode image to base64
            with open(image_file_path, 'rb') as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Determine image MIME type
            ext = os.path.splitext(image_file_path)[1].lower()
            mime_types = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            mime_type = mime_types.get(ext, 'image/jpeg')
            
            # Initialize OpenAI client
            client = OpenAI()
            
            # Define caption length requirements
            caption_requirements = {
                'short': '1 sentence (concise and punchy)',
                'medium': '2 sentences (engaging with hook)',
                'long': '3 sentences (detailed with strong hook)'
            }
            
            # Define description length requirements
            description_requirements = {
                'short': '1 paragraph (brief overview)',
                'medium': '2-3 paragraphs (detailed explanation)',
                'long': '4-5 paragraphs (comprehensive and detailed)'
            }
            
            caption_req = caption_requirements.get(caption_length, caption_requirements['medium'])
            description_req = description_requirements.get(description_length, description_requirements['medium'])
            
            # Validate and set hashtag count
            hashtag_count = max(5, min(30, hashtag_count))  # Ensure between 5 and 30
            
            # Get style configuration
            style_config = TranscribeService.STYLE_TEMPLATES.get(style, TranscribeService.STYLE_TEMPLATES['casual'])
            
            # Prepare combined prompt instructions
            combined_instructions = style_config['prompt_modifier']
            if custom_prompt:
                combined_instructions += f" ADDITIONAL CUSTOM INSTRUCTIONS: {custom_prompt}"
            
            # Create prompt for social media content generation with style
            prompt = f"""Analyze this image and generate engaging social media content for Instagram, Facebook, and YouTube.

                STYLE INSTRUCTIONS: {combined_instructions}

                Please provide:
                1. A caption ({caption_req}) - {style_config['caption_style']} with {style_config['hook_style']}
                2. A detailed description ({description_req}) - {style_config['description_style']}
                3. Exactly {hashtag_count} trending hashtags relevant to the image content

                Format the response as:

                CAPTION:
                [Your styled caption here following the style instructions]

                DESCRIPTION:
                [Your styled description here following the style instructions]

                HASHTAGS:
                [Your hashtags separated by spaces, like: #trending #photography #art]
            """
            
            # Call OpenAI Vision API for content generation
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a social media expert who creates engaging captions, descriptions, and trending hashtags for image content. You adapt your writing style based on specific instructions to match different tones and audiences. Analyze images carefully and create content that is suitable for Instagram, Facebook, and YouTube. Current style: {combined_instructions}"
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            # Parse the response using the improved parser
            content = response.choices[0].message.content
            result = TranscribeService.parse_openai_response(content)
            
            logger.info(f"Social media content generated from image: {image_file_path}")
            return result
            
        except Exception as e:
            logger.error(f"Image content generation failed: {str(e)}")
            return {"error": f"Error: {str(e)}"}
