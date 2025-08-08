# Datachop: The Ultimate Slicing Module

![GitHub stars](https://img.shields.io/github/stars/mallikmusaddiq1/datachop?style=flat-square)
![PyPI](https://img.shields.io/pypi/v/datachop?style=flat-square)
![PyPI Downloads](https://img.shields.io/pypi/dm/datachop?style=flat-square)
![GitHub top language](https://img.shields.io/github/languages/top/mallikmusaddiq1/datachop?style=flat-square)
![GitHub license](https://img.shields.io/github/license/mallikmusaddiq1/datachop?style=flat-square)
![Python versions](https://img.shields.io/pypi/pyversions/datachop?style=flat-square)

A high-performance, robust, and versatile Python library for slicing and processing various data types and files. Datachop goes beyond simple string slicing, providing a unified and intuitive API for handling everything from Unicode text to complex file formats like images, videos, audio, and documents.

This library is designed for developers who need a single, reliable tool for data extraction and manipulation, ensuring correctness and efficiency across all data types.

---

### 👤 Author Information

-   **Author:** Mallik Mohammad Musaddiq
-   **Email:** `mallikmusaddiq1@gmail.com`
-   **GitHub:** `https://github.com/mallikmusaddiq1/datachop`

---

## 🚀 Features

-   **Universal Slicing:** A single `chop()` function handles strings, lists, bytes, files, and more.
-   **Emoji-Aware Slicing:** Correctly slices strings based on **Unicode grapheme clusters**, not raw characters, ensuring emojis and multi-character symbols are handled properly.
-   **File Format Support:**
    -   **Text Files:** Slice by line, character, or byte with automatic encoding detection.
    -   **Images:** Crop and extract pixels or regions from PNG, JPEG, GIF, and TIFF files.
    -   **Videos:** Extract frames or sub-clips from MP4, AVI, MOV, and MKV files.
    -   **Audio:** Slice audio by time or frame count from MP3, WAV, and FLAC files.
    -   **Documents:** Extract pages from PDFs, paragraphs from DOCX/ODT files, and rows from CSV/JSON.
-   **Performance & Efficiency:**
    -   Uses `mmap` for efficient file I/O on large files.
    -   Thread-safe caching (`LRUCache`) for repeated operations.
    -   Asynchronous I/O and multi-threading for parallel processing.
-   **Extensibility:** A powerful plugin system allows developers to easily add support for new file types and custom slicing logic.
-   **Security & Robustness:**
    -   **Sandboxing:** Prevents path traversal attacks with a secure file handling context.
    -   **Comprehensive Error Handling:** Provides clear, actionable error codes for every possible failure (`CHOP-001`, `CHOP-002`, etc.).
-   **Dependency Management:** Optional dependencies are lazily loaded and gracefully handle missing packages.

---

## 📦 Installation

Install Datachop using pip. For advanced features, you can install optional dependencies with an `[extras]` flag.

```bash
# Basic installation for string, list, and text file slicing
pip install datachop

# Install with all optional dependencies for full functionality
pip install datachop[full]

Optional Dependencies
 * Pillow: Image processing (PNG, JPEG, etc.).
 * moviepy, ffmpeg-python: Video and GIF processing.
 * pydub: Audio processing (MP3, WAV, etc.).
 * PyPDF2, python-docx, odfpy: Document processing (PDF, DOCX, ODT).
 * redis: Distributed caching for large-scale applications.
 * tqdm: Progress bars for long-running operations.
📖 Usage
Slicing a String
Datachop's chop() function intelligently handles Unicode and emojis.
import asyncio
from datachop import chop

async def main():
    text = "Hello, World! 😊👍🚀"
    
    # Slice a single character (grapheme)
    result = await chop(text, 14) 
    # result: '👍'

    # Slice a range
    result = await chop(text, slice(7, 12))
    # result: 'World'

    # Get length of a string in graphemes
    length = await chop(text)
    # length: 17

asyncio.run(main())

Slicing a File (by line)
You can slice text files by line number, just like a list.
import asyncio
from datachop import chop

# Create a sample file
with open("sample.txt", "w", encoding="utf-8") as f:
    f.write("Line 1\nLine 2\nLine 3\nLine 4")

async def main():
    # Get a specific line
    line = await chop("sample.txt", 2, file_mode='lines')
    # line: 'Line 3'

    # Slice multiple lines
    lines = await chop("sample.txt", slice(0, 3), file_mode='lines')
    # lines: ['Line 1', 'Line 2', 'Line 3']

asyncio.run(main())

Slicing an Image
Extract pixels or crop a specific region from an image.
import asyncio
from datachop import chop, get_length
from PIL import Image

# Create a sample image
img = Image.new('RGB', (100, 100), color='blue')
img.save("sample.png")

async def main():
    # Get the total number of pixels
    pixel_count = await get_length("sample.png", file_mode='pixels')
    # pixel_count: 10000

    # Get the pixel at index 5000 (roughly center)
    pixel = await chop("sample.png", 5000)
    # pixel: (0, 0, 255)

    # Crop a 50x50 region and save it to a new file
    cropped_image = await chop(
        "sample.png", 
        region=(25, 25, 75, 75), 
        export_path="cropped.png"
    )
    # A new file 'cropped.png' is created with the cropped region.
    # The function also returns a PIL Image object.

asyncio.run(main())

Slicing a Video (by time)
Extract a sub-clip from a video file.
import asyncio
from datachop import chop

async def main():
    # This requires an existing video file like "video.mp4"
    # and the 'moviepy' and 'ffmpeg-python' dependencies.
    
    # Extract a 5-second clip from 10s to 15s and save it
    clip = await chop(
        "video.mp4", 
        slice(10, 15), 
        file_mode='time', 
        export_path="clip.mp4"
    )
    # A new file 'clip.mp4' is created.

asyncio.run(main())

📝 API Reference
chop(obj, index_or_slice, **kwargs)
The primary function for all slicing operations.
Parameters:
 * obj: The data to be sliced (string, list, file path, file object, etc.).
 * index_or_slice: An int for a single element, a slice object, or an iterable of indices.
 * **kwargs:
   * file_mode (str): Specifies how to read a file ('lines', 'bytes', 'pixels', 'frames', etc.). This is inferred if not provided.
   * region (tuple): A 4-tuple (x1, y1, x2, y2) for cropping images.
   * export_path (str): Path to save the sliced content (e.g., cropped image, video clip).
   * compression (str): Type of compression for archives ('zip', 'gz', etc.).
   * decode (str): Decode sliced bytes into a string using the specified encoding.
get_length(obj, **kwargs)
Returns the length of a sequence or a file based on the specified mode.
Parameters:
 * obj: The data object (string, list, file path).
 * **kwargs: Same as chop().
<!-- end list -->