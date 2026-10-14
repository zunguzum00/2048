import os
import requests
import argparse
from dotenv import load_dotenv
from openai import OpenAI
from elevenlabs.client import ElevenLabs
from elevenlabs import save
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

# Load environment variables
load_dotenv()

# Initialize API clients (instantiated inside functions to avoid crash if keys are missing initially)
openai_client = None
elevenlabs_client = None

def get_openai_client():
    global openai_client
    if not openai_client:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        openai_client = OpenAI(api_key=api_key)
    return openai_client

def get_elevenlabs_client():
    global elevenlabs_client
    if not elevenlabs_client:
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY environment variable is not set.")
        elevenlabs_client = ElevenLabs(api_key=api_key)
    return elevenlabs_client

def generate_script(topic, length_minutes=1):
    """Generates a video script using OpenAI."""
    print(f"Generating script for topic: {topic} (approx. {length_minutes} minutes)...")
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # Or gpt-4 if available and preferred
            messages=[
                {"role": "system", "content": f"You are a professional YouTube video script writer. Write an engaging script (about {length_minutes} minute(s) long) about the given topic. Only output the spoken text, no scene directions."},
                {"role": "user", "content": f"Topic: {topic}"}
            ]
        )
        script = response.choices[0].message.content
        print("Script generated successfully.")
        return script
    except Exception as e:
        print(f"Error generating script: {e}")
        return None

def generate_voiceover(script, output_filename="audio.mp3"):
    """Generates a voiceover using ElevenLabs API."""
    print("Generating voiceover...")
    try:
        client = get_elevenlabs_client()
        audio = client.generate(
            text=script,
            voice="Rachel", # You can change the voice ID or name here
            model="eleven_multilingual_v2"
        )
        save(audio, output_filename)
        print(f"Voiceover saved to {output_filename}")
        return output_filename
    except Exception as e:
        print(f"Error generating voiceover: {e}")
        return None

def fetch_images(topic, num_images=3):
    """Fetches images using Unsplash API."""
    print(f"Fetching {num_images} images for topic: {topic}...")
    unsplash_access_key = os.getenv("UNSPLASH_ACCESS_KEY")
    if not unsplash_access_key:
        print("UNSPLASH_ACCESS_KEY not found in environment variables. Cannot fetch images.")
        return []

    url = f"https://api.unsplash.com/search/photos?query={topic}&client_id={unsplash_access_key}&per_page={num_images}&orientation=landscape"
    image_paths = []

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        for i, result in enumerate(data.get('results', [])):
            image_url = result['urls']['regular']
            img_data = requests.get(image_url).content
            filename = f"image_{i}.jpg"
            with open(filename, 'wb') as handler:
                handler.write(img_data)
            image_paths.append(filename)
            print(f"Downloaded {filename}")

        return image_paths
    except Exception as e:
        print(f"Error fetching images: {e}")
        return []

def create_video(audio_path, image_paths, output_filename="final_video.mp4"):
    """Combines images and audio into a video using MoviePy."""
    print("Compiling video...")
    if not image_paths:
        print("No images found to create video.")
        return False

    try:
        audio_clip = AudioFileClip(audio_path)
        audio_duration = audio_clip.duration

        # Calculate how long each image should be shown
        duration_per_image = audio_duration / len(image_paths)

        clips = []
        for img_path in image_paths:
            # Resize image to standard 1080p width to prevent moviepy errors with different sizes
            clip = ImageClip(img_path).with_duration(duration_per_image).resized(width=1920)
            clips.append(clip)

        video = concatenate_videoclips(clips, method="compose")
        video = video.with_audio(audio_clip)

        # Write the result to a file
        video.write_videofile(output_filename, fps=24, codec="libx264", audio_codec="aac")
        print(f"Video successfully saved to {output_filename}")

        # Cleanup clips to release file handles
        for clip in clips:
            clip.close()
        audio_clip.close()
        video.close()

        return True
    except Exception as e:
        print(f"Error creating video: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Generate a YouTube video using AI.")
    parser.add_argument("topic", type=str, help="The topic for the video.")
    parser.add_argument("--length", type=int, default=1, help="Desired length of the video in minutes (approx).")
    args = parser.parse_args()

    topic = args.topic
    length = args.length

    # 1. Generate Script
    script = generate_script(topic, length)
    if not script:
        return

    # 2. Generate Voiceover
    audio_file = generate_voiceover(script)
    if not audio_file:
        return

    # 3. Fetch Images
    image_files = fetch_images(topic)
    if not image_files:
        # Fallback if no images: generate a blank video or stop
        print("Video generation stopped due to missing images.")
        return

    # 4. Create Video
    create_video(audio_file, image_files)

    # Optional: Cleanup temporary files (audio.mp3, image_*.jpg)
    print("Process complete!")

if __name__ == "__main__":
    main()
