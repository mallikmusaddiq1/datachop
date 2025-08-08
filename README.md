# Datachop: The Ultimate Slicing Module

![GitHub stars](https://img.shields.io/github/stars/mallikmusaddiq1/datachop?style=flat-square)
![PyPI](https://img.shields.io/pypi/v/datachop?style=flat-square)
![GitHub license](https://img.shields.io/github/license/mallikmusaddiq1/datachop?style=flat-square)
![Python versions](https://img.shields.io/pypi/pyversions/datachop?style=flat-square)
![PyPI Downloads](https://img.shields.io/pypi/dm/datachop?style=flat-square)
![GitHub top language](https://img.shields.io/github/languages/top/mallikmusaddiq1/datachop?style=flat-square)

A high-performance, robust Python library for slicing and processing various data types and files. Datachop goes beyond simple string slicing, providing a unified and intuitive API for handling everything from Unicode text to complex file format like images.

This library is designed for developers who need a single, reliable tool for data extraction and manipulation, ensuring correctness and efficiency across all data types.

---

### 👤 Author Information

-   **Author:** Mallik Mohammad Musaddiq
-   **Email:** `mallikmusaddiq1@gmail.com`
-   **GitHub:** `https://github.com/mallikmusaddiq1/datachop`

## Key Features

- **Universal Slicing**: A single function, `chop()`, handles strings, bytes, lists, and files.
- **Unicode Grapheme Support**: Correctly slices strings containing multi-character emojis and ligatures.
- **Comprehensive File Handling**:
  - **Text Files**: Slice by line or character.
  - **Binary Files**: Slice by byte, with high-performance `mmap` support for large files.
  - **Specialized Files**: Built-in support for images (`.png`, `.jpeg`, `.gif`), CSV, and JSON.
- **Advanced Slicing Operations**: Supports single indices, standard slice objects, and iterables of indices.
- **Robust Error Handling**: Specific, descriptive error classes provide clear feedback.
- **Security & Performance**:
  - **Path Sandboxing**: Prevents path traversal vulnerabilities for file operations.
  - **Thread-safe Caching**: Utilizes a thread-safe LRU cache for frequently accessed data, with optional Redis support.
  - **Efficient Large File Processing**: Leverages `mmap` and streaming for memory-efficient handling.
- **Extensible Plugin System**: Easily add support for new data formats and file types.
- **Optional Dependencies**: Features are gracefully disabled if optional libraries are not installed.
- **Asynchronous I/O Ready**: The architecture is designed to easily integrate with `asyncio`.

## Installation

You can install DataChop using pip:

```bash
pip install datachop

For advanced features like Unicode grapheme support, image slicing, or encoding detection, install the optional dependencies:
pip install datachop[full]

This will install regex, Pillow, numpy, and charset-normalizer.
Quick Start
import datachop as dc

# 1. String Slicing with Unicode Support
string_data = "Hello😊👍 world!"
result = dc.chop(string_data, slice(5, 7))
# Output: "😊👍"

# 2. File Handling (by lines)
# Assume 'sample.txt' contains:
# Line 1
# Line 2
# Line 3
lines = dc.chop("sample.txt", slice(1, 3), file_mode='lines')
# Output: ['Line 2', 'Line 3']

# 3. Image Slicing (requires Pillow and numpy)
# Assume 'image.png' is a 100x100 pixel image
cropped_image = dc.chop("image.png", (0, 0, 10, 10))
# 'cropped_image' is a PIL Image object of size 10x10

# 4. Get Length (Universal)
length_of_file = dc.get_length("sample.txt", file_mode='lines')
# Output: 3
length_of_string = dc.get_length(string_data)
# Output: 13 (correctly counts graphemes)

API Reference
chop(obj, index_or_slice=None, **kwargs)
The main function for slicing.
Parameters:
 * obj: The data source. Can be a string, list, bytes, file path, or a file-like object.
 * index_or_slice:
   * An integer index (e.g., 5).
   * A slice object (e.g., slice(0, 5)).
   * An Iterable of indices (e.g., [0, 2, 5]).
   * A tuple (x1, y1, x2, y2) for image regions.
 * **kwargs:
   * file_mode: str, e.g., 'lines', 'bytes', 'pixels'.
   * encoding: str, character encoding for text files.
   * export_path: str, path to save results (e.g., a cropped image).
get_length(obj, file_mode=None)
Returns the length of a sequence or file.
Parameters:
 * obj: The object to measure.
 * file_mode: str, e.g., 'lines', 'bytes', 'pixels'.
Extensibility
DataChop's plugin system allows you to add support for new data formats. Simply create a class that inherits from ChopPlugin and implement the process() method.
chop_plugins/my_plugin.py:
from datachop import ChopPlugin, register_plugin, ChopDependencyError

class CSVPlugin(ChopPlugin):
    def __init__(self):
        super().__init__(
            name="CSV",
            modes=["rows"],
            extensions=[".csv"],
            dependencies=[],
            priority=5
        )

    def process(self, data_source, mode):
        import csv
        with open(data_source, 'r') as f:
            reader = csv.reader(f)
            # Example: returns the number of rows
            return sum(1 for _ in reader)

# This is the entry point for the plugin system
plugin = CSVPlugin()

Plugins in the chop_plugins directory are automatically discovered and loaded.
Contribution
We welcome contributions! If you have a feature request, bug report, or want to contribute code, please check out our contribution guidelines.

---

License: MIT
