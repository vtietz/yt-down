# YouTube Video Downloader

A Python script to download YouTube videos in the best available quality by downloading video and audio streams separately and merging them.

## Features

- Download videos by ID, URL, or search query
- Separate video/audio stream download for best quality
- Interactive quality selection
- Automatic best quality selection (optional)
- Custom output path support
- Logging functionality
- Cookie support for age-restricted content

## Requirements

- Python 3.x
- yt-dlp
- ffmpeg

## Installation

1. Clone or download this repository
2. Install required packages:
```sh
pip install yt-dlp
```
3. Install ffmpeg and ensure it's in your system PATH

## Usage

Basic usage:

```sh
python yt.py <video_id|url|search_query> [options]
```

### Options

- `--skip-quality`, `-s`: Skip quality selection and use best quality
- `--output`, `-o`: Output file path/name (default: download/<title>.mp4)
- `--max-results`, `-m`: Maximum number of search results to download (default: 1)
- `--suffix`, `-x`: Suffix to add to the output filename
- `--force`, `-f`: Force overwrite existing file
- `--max-res`: Limit maximum resolution, e.g. "720"

### Examples

Download by video ID:
```sh
python yt.py dQw4w9WgXcQ
```

Download by URL:
```sh
python yt.py https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

Search and download:
```sh
python yt.py "never gonna give you up"
```

Search and download multiple results:
```sh
python yt.py "never gonna give you up" --max-results 5
```

Skip quality selection (use best quality):
```sh
python yt.py --skip-quality "never gonna give you up"
```

Specify output file:
```sh
python yt.py -o "my_video.mp4" "never gonna give you up"
```

Add suffix to filename:
```sh
python yt.py --suffix "-trailer" "never gonna give you up"
```

Force overwrite existing file:
```sh
python yt.py --force "never gonna give you up"
```

Limit maximum resolution:
```sh
python yt.py --max-res 720 "never gonna give you up"
```

## Integration with tinyMediaManager

To use this script with tinyMediaManager for automatic trailer downloads:

1. Open tinyMediaManager settings
2. Go to "Post Processing" section
3. Add a new post-processing entry:
   - Name: "Download Trailer"
   - Path: Path to Python executable (e.g. `C:\Users\[USERNAME]\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\python.exe`)
   - Arguments: 
   ```
   "[PATH_TO_YOUR_SCRIPT]\yt-down\yt.py" "${movie.title} trailer german deutsch" -s -o "${movie.mainVideoFile.path}\${movie.mainVideoFile.basename}-trailer"
   ```

This will automatically search for and download the trailer in the best quality, saving it next to your movie file with "-trailer" suffix.

## Notes

- Downloads are saved in the `download` directory by default
- Logs are stored in the `logs` directory
- Uses `cookies.txt` for authenticated access if available
- Temporary files are automatically cleaned up after merging