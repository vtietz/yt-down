import yt_dlp
import sys
import subprocess
import os
import re
import argparse
import logging
from datetime import datetime
from urllib.parse import urlparse, parse_qs

def setup_logging():
    log_dir = ensure_download_dir(os.path.join(os.path.dirname(__file__), 'logs'))
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'youtube_dl_{timestamp}.log')
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger('youtube_dl')

def sanitize_filename(filename, max_length=150):
    """Sanitize filename and limit length"""
    # Remove invalid characters and replace with underscore
    clean = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Limit length while preserving file extension
    if len(clean) > max_length:
        clean = clean[:max_length-3] + "..."
    return clean

def get_unique_filename(base_path, title, suffix=""):
    """Generate unique filename based on title and optional suffix"""
    base_name = sanitize_filename(title)
    if suffix:
        base_name = f"{base_name}{suffix}"
    
    file_path = os.path.join(base_path, f"{base_name}.mp4")
    counter = 1
    
    while os.path.exists(file_path):
        file_path = os.path.join(base_path, f"{base_name}_{counter}.mp4")
        counter += 1
    
    return file_path

def search_youtube(query, max_results=1):
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'playlist_items': f'1-{max_results}',  # Limit the number of results
        'default_search': f'ytsearch{max_results}'  # Request more results
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            result = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            if 'entries' in result:
                videos = []
                for entry in result['entries']:
                    if entry:  # Some entries might be None
                        videos.append({'id': entry['id'], 'title': entry['title']})
                        if len(videos) >= max_results:  # Ensure we don't exceed requested number
                            break
                return videos
            logger.warning("No search results found")
            return None
        except Exception as e:
            logger.error(f"Search error: {e}")
            return None

def get_video_id(input_string, max_results=1):
    # Handle URL or direct video ID
    if 'youtube.com' in input_string or 'youtu.be' in input_string:
        parsed_url = urlparse(input_string)
        if 'youtube.com' in input_string:
            return [{'id': parse_qs(parsed_url.query).get('v', [None])[0], 'title': None}]
        else:
            return [{'id': parsed_url.path[1:], 'title': None}]
    elif len(input_string) == 11:
        return [{'id': input_string, 'title': None}]
    else:
        results = search_youtube(input_string, max_results)
        if results:
            for video in results:
                logger.info(f"Found video: {video['title']}")
            return results
        else:
            logger.warning("No videos found for the search query")
            return None

def ensure_download_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)
    return path

def check_file_exists(filepath, force_overwrite=False):
    """Check if file exists and handle overwrite choice"""
    if (os.path.exists(filepath)):
        if (force_overwrite):
            logger.info(f"Force overwrite enabled, will overwrite: {filepath}")
            return True
        choice = input(f"File already exists: {filepath}\nDo you want to overwrite? [y/N]: ")
        if (choice.lower() != 'y'):
            logger.info("Download cancelled by user - file exists")
            return False
        logger.info("User chose to overwrite existing file")
        return True
    return True

def get_resolution_height(resolution):
    """Convert resolution string to height number (e.g., '1080p' -> 1080)"""
    if not resolution:
        return None
    # Handle common resolution strings
    if 'x' in resolution:
        try:
            width, height = map(int, resolution.split('x'))
            return height
        except:
            pass
    match = re.match(r'(\d+)p?', resolution.lower())
    return int(match.group(1)) if match else None

def sort_formats_by_resolution(formats):
    """Sort formats by resolution height"""
    def get_height(fmt):
        res = fmt.get('resolution', '')
        height = get_resolution_height(res)
        return height if height else 0
    return sorted(formats, key=get_height)

def sort_formats_by_quality(formats):
    """Sort formats by resolution and then by quality (bitrate/filesize)"""
    def get_quality_score(fmt):
        height = get_resolution_height(fmt.get('resolution', '')) or 0
        # Prefer higher bitrate within same resolution
        bitrate = fmt.get('tbr', 0) or fmt.get('vbr', 0) or 0
        # If no bitrate, use filesize as fallback
        filesize = fmt.get('filesize', 0) or 0
        # Return tuple for sorting: (height, bitrate, filesize)
        return (height, bitrate, filesize)
    
    return sorted(formats, key=get_quality_score)

def download_video_and_audio_separately(video_info, skip_quality_selection=False, output_dir=None, suffix="", force_overwrite=False, max_resolution=None):
    try:
        video_id = video_info['id']
        url = f'https://www.youtube.com/watch?v={video_id}'
        logger.info(f"Starting download for video: {url}")
        
        # Fetch format list with video-only and audio-only filtering
        ydl_opts_info = {
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
            logger.error("No suitable video or audio formats found.")
            return
            
        # Filter by resolution if specified
        if max_resolution:
            max_height = get_resolution_height(max_resolution)
            if max_height:
                # Sort formats by resolution and quality before filtering
                video_formats = sort_formats_by_quality(video_formats)
                video_formats = [f for f in video_formats if get_resolution_height(f.get('resolution', '')) and get_resolution_height(f.get('resolution', '')) <= max_height]
                if not video_formats:
                    raise Exception(f"No video formats found for resolution {max_resolution} or below")
                
                # Group formats by resolution
                formats_by_res = {}
                for fmt in video_formats:
                    res = fmt.get('resolution', '')
                    if res not in formats_by_res:
                        formats_by_res[res] = []
                    formats_by_res[res].append(fmt)
                
                # Log available formats grouped by resolution
                logger.info("Available formats by resolution:")
                for res, fmts in formats_by_res.items():
                    best_fmt = sorted(fmts, key=lambda f: (f.get('tbr', 0) or f.get('vbr', 0) or f.get('filesize', 0) or 0))[-1]
                    logger.info(f"  {res}: {len(fmts)} formats, selected format_id: {best_fmt['format_id']} "
                              f"(bitrate: {best_fmt.get('tbr', 'N/A')}, size: {best_fmt.get('filesize', 'N/A')})")
                
                # Get the highest resolution available within limit
                max_res_available = max(formats_by_res.keys(), key=lambda r: get_resolution_height(r) or 0)
                # Get the best quality format for that resolution
                best_formats = formats_by_res[max_res_available]
                video_formats = [sorted(best_formats, key=lambda f: (f.get('tbr', 0) or f.get('vbr', 0) or f.get('filesize', 0) or 0))[-1]]
                
                logger.info(f"Selected best format at {max_res_available}")

        # Set default best video and audio formats (now properly sorted)
        best_video_format = video_formats[-1]['format_id']
        best_audio_format = audio_formats[0]['format_id']
        logger.info(f"Default video format: {video_formats[-1]['ext']} {video_formats[-1]['resolution']}")
        logger.info(f"Default audio format: {audio_formats[0]['ext']}")
        
        # If max_resolution is set, skip manual selection regardless of other settings
        if max_resolution:
            selected_video_format = best_video_format
            selected_audio_format = best_audio_format
        else:
            if skip_quality_selection:
                selected_video_format = best_video_format
                selected_audio_format = best_audio_format
            else:
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
        download_dir = ensure_download_dir(os.path.join(os.path.dirname(__file__), 'download'))
        target_dir = output_dir if output_dir else download_dir
        ensure_download_dir(target_dir)
        
        # Get video title if not provided
        if not video_info['title']:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                video_info['title'] = info['title']
        
        output_file = get_unique_filename(target_dir, video_info['title'], suffix)
        temp_video = os.path.join(download_dir, f"{video_id}_temp_video.mp4")
        temp_audio = os.path.join(download_dir, f"{video_id}_temp_audio.mp4")
        
        ydl_opts_video = {
            'outtmpl': temp_video,
            'format': selected_video_format
        }
        
        ydl_opts_audio = {
            'outtmpl': temp_audio,
            'format': selected_audio_format
        }
        
        # Download video
        logger.info(f"Downloading video format {selected_video_format}")
        with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
            ydl.download([url])
        
        # Download audio
        logger.info(f"Downloading audio format {selected_audio_format}")
        with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
            ydl.download([url])
        
        # Merge video and audio using ffmpeg
        logger.info("Merging video and audio using ffmpeg...")
        logger.info(f"Source video: {temp_video}")
        logger.info(f"Source audio: {temp_audio}")
        logger.info(f"Target file: {output_file}")
        
        # Ensure target directory exists
        target_dir = os.path.dirname(output_file)
        if not os.path.exists(target_dir):
            logger.info(f"Creating target directory: {target_dir}")
            os.makedirs(target_dir, exist_ok=True)
        
        # Check if source files exist
        if not os.path.exists(temp_video):
            raise FileNotFoundError(f"Video file not found: {temp_video}")
        if not os.path.exists(temp_audio):
            raise FileNotFoundError(f"Audio file not found: {temp_audio}")
        
        # Run ffmpeg with output capture
        result = subprocess.run([
            'ffmpeg', '-i', temp_video, '-i', temp_audio,
            '-c:v', 'copy', '-c:a', 'aac', '-strict', 'experimental', output_file
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            raise Exception(f"FFmpeg failed with return code {result.returncode}")
        
        # Verify the output file exists and has size > 0
        if not os.path.exists(output_file):
            raise FileNotFoundError(f"Output file was not created: {output_file}")
        if os.path.getsize(output_file) == 0:
            raise Exception(f"Output file was created but is empty: {output_file}")
            
        logger.info(f"FFmpeg merge successful. Output file size: {os.path.getsize(output_file)} bytes")
        
        # Cleanup temporary files
        try:
            os.remove(temp_video)
            os.remove(temp_audio)
            logger.info("Temporary files cleaned up successfully")
        except Exception as e:
            logger.warning(f"Error cleaning up temporary files: {e}")
        
        logger.info(f"Download and merge completed! Final file: {output_file}")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        # Try to clean up temp files even if there was an error
        for temp_file in [temp_video, temp_audio]:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
        raise  # Re-raise the exception after cleanup

if __name__ == '__main__':
    logger = setup_logging()
    logger.info("YouTube Downloader started")
    logger.info(f"Raw command line arguments: {sys.argv[1:]}")  # Skip first arg (script name)
       
    parser = argparse.ArgumentParser(description='''
    YouTube Video Downloader - Download videos with separate video/audio streams for best quality.
    
    Examples:
        Download by video ID:
            python yt.py dQw4w9WgXcQ
        
        Download by URL:
            python yt.py https://www.youtube.com/watch?v=dQw4w9WgXcQ
        
        Search and download (first result):
            python yt.py "never gonna give you up"
        
        Search and download multiple results:
            python yt.py -n 5 "game trailer 2024"
        
        Skip quality selection (use best quality):
            python yt.py -s "never gonna give you up"
            
        Limit maximum resolution:
            python yt.py --max-res 720p "game trailer 2024"
            python yt.py --max-res 1080p "game trailer 2024"
            
        Specify output directory:
            python yt.py -o "/path/to/directory" "never gonna give you up"
            
        Add suffix to filename:
            python yt.py --suffix="-trailer" "game trailer 2024"
            python yt.py --suffix="-other suffix" "video name"
            
        Force overwrite existing files:
            python yt.py -f "never gonna give you up"
    ''', formatter_class=argparse.RawDescriptionHelpFormatter)
    
    parser.add_argument('input', nargs='?', help='YouTube video ID, URL, or search query')
    parser.add_argument('--skip-quality', '-s', action='store_true', 
                        help='Skip quality selection and use best quality')
    parser.add_argument('--output', '-o', metavar='DIR',
                        help='Output directory (default: download/)')
    parser.add_argument('--force', '-f', action='store_true',
                        help='Force overwrite if output file already exists')
    parser.add_argument('--number', '-n', type=int, default=1,
                        help='Number of search results to download (1-50, default: 1)')
    parser.add_argument('--suffix', metavar='SUFFIX', type=str, default='',
                        help='Suffix to add to filename (e.g., "--suffix=-trailer")')
    parser.add_argument('--max-res', metavar='RES',
                        help='Maximum resolution (e.g., 720p, 1080p). Overrides quality selection.')
    
    args = parser.parse_args()
    
    # Log the arguments
    logger.info("Arguments:")
    logger.info(f"  Input: {args.input}")
    logger.info(f"  Skip quality selection: {args.skip_quality}")
    logger.info(f"  Output path: {args.output}")
    logger.info(f"  Force overwrite: {args.force}")
    logger.info(f"  Number of search results: {args.number}")
    logger.info(f"  Filename suffix: {args.suffix}")
    logger.info(f"  Maximum resolution: {args.max_res}")
    
    # Validate number of results
    args.number = max(1, min(50, args.number))  # Limit between 1 and 50
    logger.info(f"Will download up to {args.number} videos")
    
    # Validate max resolution if provided
    if args.max_res and not get_resolution_height(args.max_res):
        logger.error(f"Invalid resolution format: {args.max_res}. Use format like 720p or 1080p")
        sys.exit(1)
    
    if not args.input:
        parser.print_help()
        logger.warning("No input provided")
        sys.exit(1)
        
    videos = get_video_id(args.input, args.number)
    if videos:
        success_count = 0
        fail_count = 0
        logger.info(f"Found {len(videos)} videos to process")
        
        for i, video in enumerate(videos, 1):
            logger.info(f"Processing video {i} of {len(videos)}: {video.get('title', video['id'])}")
            try:
                download_video_and_audio_separately(
                    video, 
                    args.skip_quality, 
                    args.output,
                    args.suffix,
                    args.force,
                    args.max_res
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to process video: {e}")
                fail_count += 1
                continue  # Move to next video
        
        # Summary at the end
        logger.info("Download summary:")
        logger.info(f"  Successfully downloaded: {success_count}")
        logger.info(f"  Failed downloads: {fail_count}")
        logger.info(f"  Total attempted: {len(videos)}")
        
        if fail_count > 0:
            sys.exit(1)  # Exit with error if any downloads failed
    else:
        parser.print_help()
        logger.error("Could not get video ID")
        sys.exit(1)
