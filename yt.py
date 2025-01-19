import yt_dlp
import sys
import subprocess
import os
import re

def sanitize_filename(filename):
    # Remove invalid characters for Windows filenames
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

def download_video_and_audio_separately(video_id):
    try:
        # Construct the YouTube URL from the video ID
        url = f'https://www.youtube.com/watch?v={video_id}'
        
        # Fetch format list with video-only and audio-only filtering
        ydl_opts_info = {
            'cookiefile': 'cookies.txt',
            'listformats': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            video_title = sanitize_filename(info.get('title', video_id))
        
        # Filter video-only formats (exclude unknowns)
        video_formats = [f for f in formats if f.get('vcodec') != 'none' and f.get('acodec') == 'none' and f.get('resolution') != 'unknown']
        audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
        
        if not video_formats or not audio_formats:
            print("No suitable video or audio formats found.")
            return
        
        # Set default best video and audio formats
        best_video_format = video_formats[-1]['format_id']
        best_audio_format = audio_formats[0]['format_id']
        print(f"Default video format: {video_formats[-1]['ext']} {video_formats[-1]['resolution']}")
        print(f"Default audio format: {audio_formats[0]['ext']}")
        
        choice = input("Press Enter to use default formats [default: best quality] or type 'manual' to select manually: ")
        if choice == '':
            selected_video_format = best_video_format
            selected_audio_format = best_audio_format
        else:
            print("Available video-only formats:")
            for i, fmt in enumerate(video_formats, start=1):
                resolution = fmt.get('resolution', 'unknown')
                ext = fmt.get('ext', 'unknown')
                filesize = fmt.get('filesize', 'unknown')
                print(f"{i}. {ext} {resolution} {filesize}B")
            
            video_choice = input(f"Enter the number of the video format you want to download [default: {len(video_formats)}]: ")
            video_choice = int(video_choice) if video_choice else len(video_formats)
            if 1 <= video_choice <= len(video_formats):
                selected_video_format = video_formats[video_choice - 1]['format_id']
            else:
                print("Invalid choice.")
                return
            
            print("Available audio-only formats:")
            for i, fmt in enumerate(audio_formats, start=1):
                ext = fmt.get('ext', 'unknown')
                filesize = fmt.get('filesize', 'unknown')
                print(f"{i}. {ext} {filesize}B")
            
            audio_choice = input(f"Enter the number of the audio format you want to download [default: 1]: ")
            audio_choice = int(audio_choice) if audio_choice else 1
            if 1 <= audio_choice <= len(audio_formats):
                selected_audio_format = audio_formats[audio_choice - 1]['format_id']
            else:
                print("Invalid choice.")
                return
        
        # Define download options for video and audio
        video_file = f"{video_title}_video.mp4"
        audio_file = f"{video_title}_audio.mp4"
        output_file = f"{video_title}.mp4"
        
        ydl_opts_video = {
            'outtmpl': video_file,
            'cookiefile': 'cookies.txt',
            'format': selected_video_format
        }
        
        ydl_opts_audio = {
            'outtmpl': audio_file,
            'cookiefile': 'cookies.txt',
            'format': selected_audio_format
        }
        
        # Download video
        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
            print(f"Downloading video format {selected_video_format}")
            ydl.download([url])
        
        # Download audio
        with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
            print(f"Downloading audio format {selected_audio_format}")
            ydl.download([url])
        
        # Merge video and audio using ffmpeg
        print("Merging video and audio using ffmpeg...")
        subprocess.run([
            'ffmpeg', '-i', video_file, '-i', audio_file,
            '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental', output_file
        ])
        
        # Cleanup temporary files
        os.remove(video_file)
        os.remove(audio_file)
        
        print(f"Download and merge completed! Final file: {output_file}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python download_youtube.py <video_id>")
    else:
        video_id = sys.argv[1]
        download_video_and_audio_separately(video_id)
