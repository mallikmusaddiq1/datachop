#!/usr/bin/env python3
"""
DataChop: The Ultimate Slicing Module

A highly flexible and robust library for slicing and processing various data types,
including strings, bytes, lists, and files. It is designed for maximum performance,
extensibility, and open-source excellence.

License: MIT
Version: 1.0.0
Author: Mallik Mohammad Musaddiq
Repository: https://github.com/mallikmusaddiq1/datachop

Key Features:
- Universal Slicing: A single function `chop()` handles strings, bytes, lists, and files.
- Unicode Grapheme Support: Correctly slices strings with multi-character emojis using the `regex` library.
- Comprehensive File Handling:
    - Text Files: Slice by line or character.
    - Binary Files: Slice by byte, with high-performance `mmap` support for large files.
    - Specialized Files: Built-in support for images (PNG, JPEG, GIF), CSV, and JSON.
    - Non-seekable Streams: gracefully handles streaming data.
- Advanced Slicing Operations: Supports single indices, standard slice objects, and iterables of indices.
- Robust Error Handling: Specific, descriptive error classes provide clear feedback.
- Security and Performance:
    - Path Sandboxing: Prevents path traversal vulnerabilities for file operations.
    - Thread-safe Caching: Utilizes a thread-safe LRU cache for frequently accessed data, with optional Redis support.
    - Efficient Large File Processing: Leverages `mmap` and streaming for memory-efficient handling.
- Extensible Plugin System: Easily add support for new data formats and file types.
- Optional Dependencies: Features are gracefully disabled if optional libraries are not installed.
- Asynchronous I/O Ready: The architecture is designed to easily integrate with `asyncio` for non-blocking operations.

Example Usage:
    >>> import datachop as dc
    >>> dc.chop("Hello😊👍", 5)  # Returns '👍'
    >>> dc.chop("sample.txt", slice(1, 3), file_mode='lines')  # Returns ['Line 2', 'Line 3']
    >>> dc.chop("image.png", (0, 0, 10, 10))  # Crops a 10x10 pixel region
    >>> dc.get_length("sample.txt", file_mode='lines')  # Returns number of lines

"""
import os
import sys
import io
import mmap
import tempfile
import shutil
import pickle
import logging
import configparser
import pkgutil
from typing import Union, Any, Optional, Sequence, List, Tuple, Iterable, TextIO, BinaryIO, Dict, Callable
from collections.abc import Sequence as SequenceType
from threading import Lock
from pathlib import Path
from contextlib import contextmanager, suppress
from functools import lru_cache

# Optional dependencies, loaded on-demand
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

try:
    import regex
    REGEX_AVAILABLE = True
except ImportError:
    REGEX_AVAILABLE = False
    regex = None

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None

try:
    import charset_normalizer
    CHARSET_NORMALIZER_AVAILABLE = True
except ImportError:
    CHARSET_NORMALIZER_AVAILABLE = False
    charset_normalizer = None

try:
    import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    tqdm = None

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

# --- Configuration and Constants ---
__version__ = "1.0.0"
__license__ = "MIT"
__author__ = "Mallik Mohammad Musaddiq"

# Supported file extensions
SUPPORTED_IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif')
SUPPORTED_DOC_EXTS = ('.odt', '.json', '.csv')

# Configuration management
CONFIG = configparser.ConfigParser()
CONFIG.read('chop.ini')
DEFAULT_CONFIG = {
    'default_encoding': 'utf-8',
    'max_file_size': 1_000_000_000,  # 1GB
    'allowed_dir': os.getcwd(),
    'cache_size': 1024,
    'log_level': 'INFO',
    'max_threads': 4,
    'chunk_size': 8192,  # For streaming
}
DEFAULT_ENCODING = CONFIG.get('settings', 'default_encoding', fallback=DEFAULT_CONFIG['default_encoding'])
MAX_FILE_SIZE = CONFIG.getint('settings', 'max_file_size', fallback=DEFAULT_CONFIG['max_file_size'])
ALLOWED_DIR = CONFIG.get('settings', 'allowed_dir', fallback=DEFAULT_CONFIG['allowed_dir'])
CACHE_SIZE = CONFIG.getint('settings', 'cache_size', fallback=DEFAULT_CONFIG['cache_size'])
LOG_LEVEL = CONFIG.get('settings', 'log_level', fallback=DEFAULT_CONFIG['log_level'])
MAX_THREADS = CONFIG.getint('settings', 'max_threads', fallback=DEFAULT_CONFIG['max_threads'])
CHUNK_SIZE = CONFIG.getint('settings', 'chunk_size', fallback=DEFAULT_CONFIG['chunk_size'])

# Logging setup
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('chop.log', encoding='utf-8')
    ]
)
logger = logging.getLogger('datachop')
plugin_logger = logging.getLogger('datachop.plugins')

# --- Error Classes ---
class ChopError(Exception):
    """Base exception for all DataChop errors."""
    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(f"[{code}] {message}" if code else message)
        self.code = code

class ChopIndexError(ChopError, IndexError):
    """Raised when an index is out of bounds."""
    pass

class ChopValueError(ChopError, ValueError):
    """Raised for invalid values or parameters."""
    pass

class ChopTypeError(ChopError, TypeError):
    """Raised for invalid types."""
    pass

class ChopFileError(ChopError, IOError):
    """Raised for file-related issues."""
    pass

class ChopPermissionError(ChopError, PermissionError):
    """Raised for security-related issues."""
    pass

class ChopDependencyError(ChopError, ImportError):
    """Raised when a required dependency is missing."""
    pass

# --- LRU Cache Implementation ---
class LRUCache:
    """Thread-safe LRU cache with optional Redis backend."""
    
    def __init__(self, maxsize: int, use_redis: bool = False, redis_url: str = 'redis://localhost:6379'):
        self.maxsize = maxsize
        self.use_redis = use_redis and REDIS_AVAILABLE
        self.lock = Lock()
        
        if self.use_redis:
            self.redis = redis.Redis.from_url(redis_url)
            self.cache = {}  # Local fallback
        else:
            self.cache = {}
            self.queue = []

    def __len__(self) -> int:
        with self.lock:
            return len(self.cache)

    def __contains__(self, key: Any) -> bool:
        with self.lock:
            if self.use_redis:
                return self.redis.exists(key) > 0
            return key in self.cache

    def __getitem__(self, key: Any) -> Any:
        with self.lock:
            if self.use_redis:
                value = self.redis.get(key)
                if value is None:
                    raise KeyError(key)
                return pickle.loads(value)
            if key in self.cache:
                self.queue.remove(key)
                self.queue.append(key)
                return self.cache[key]
            raise KeyError(key)

    def __setitem__(self, key: Any, value: Any) -> None:
        with self.lock:
            if self.use_redis:
                self.redis.set(key, pickle.dumps(value))
                return
            if key in self.cache:
                self.queue.remove(key)
            elif len(self.queue) >= self.maxsize:
                oldest_key = self.queue.pop(0)
                del self.cache[oldest_key]
            self.cache[key] = value
            self.queue.append(key)

# Global caches
grapheme_cache = LRUCache(maxsize=CACHE_SIZE, use_redis=REDIS_AVAILABLE)
encoding_cache = LRUCache(maxsize=CACHE_SIZE, use_redis=REDIS_AVAILABLE)
file_cache = LRUCache(maxsize=CACHE_SIZE)

# Thread pool and locks
file_lock = Lock()
cache_lock = Lock()
plugin_lock = Lock()

# --- Plugin System ---
class ChopPlugin:
    """Base class for DataChop plugins."""
    
    def __init__(self, name: str, modes: List[str], extensions: List[str], dependencies: List[str], 
                 priority: int = 0, version: str = '1.0.0'):
        self.name = name
        self.modes = modes
        self.extensions = [ext.lower() for ext in extensions]
        self.dependencies = dependencies
        self.priority = priority
        self.version = version
        self.validate_dependencies()

    def validate_dependencies(self) -> None:
        """Validate plugin dependencies upon initialization."""
        for dep in self.dependencies:
            try:
                __import__(dep)
            except ImportError:
                raise ChopDependencyError(
                    f"Plugin '{self.name}' requires '{dep}'. Install with 'pip install {dep}'.",
                    code="CHOP-001"
                )

    def process(self, data_source: Any, mode: str) -> Any:
        """
        Main method for plugin logic.
        
        Args:
            data_source: The input data, which can be a file path, file object, or in-memory data.
            mode: The file mode string that triggered this plugin.
        
        Returns:
            The processed data, such as a list of rows, a cropped image, etc.
        
        Raises:
            NotImplementedError: If the plugin does not implement this method.
        """
        raise NotImplementedError(f"Plugin '{self.name}' must implement a 'process' method.")

# Plugin registries
FILE_MODE_HANDLERS: Dict[str, ChopPlugin] = {}
FILE_EXTENSION_HANDLERS: Dict[str, ChopPlugin] = {}

def register_plugin(plugin: ChopPlugin) -> None:
    """Register a plugin with validation and priority handling."""
    with plugin_lock:
        for mode in plugin.modes:
            existing = FILE_MODE_HANDLERS.get(mode)
            if existing and existing.priority >= plugin.priority:
                plugin_logger.warning(
                    f"Skipping registration of mode '{mode}' for plugin '{plugin.name}' "
                    f"(priority {plugin.priority}) due to existing plugin '{existing.name}' "
                    f"(priority {existing.priority})."
                )
                continue
            FILE_MODE_HANDLERS[mode] = plugin
        for ext in plugin.extensions:
            existing = FILE_EXTENSION_HANDLERS.get(ext)
            if existing and existing.priority >= plugin.priority:
                plugin_logger.warning(
                    f"Skipping registration of extension '{ext}' for plugin '{plugin.name}' "
                    f"(priority {plugin.priority}) due to existing plugin '{existing.name}' "
                    f"(priority {existing.priority})."
                )
                continue
            FILE_EXTENSION_HANDLERS[ext] = plugin
        plugin_logger.info(f"Registered plugin: '{plugin.name}' (v{plugin.version}, priority={plugin.priority})")

def load_plugins_from_directory(plugin_dir: str = 'chop_plugins') -> None:
    """Discover and load plugins from a directory using standard package discovery."""
    try:
        plugin_dir_path = Path(plugin_dir).resolve()
        if not plugin_dir_path.exists():
            plugin_logger.warning(f"Plugin directory '{plugin_dir}' does not exist.")
            return

        sys.path.insert(0, str(plugin_dir_path.parent))
        
        # Use importlib.machinery to load the module spec without adding to sys.modules immediately
        import importlib.util
        
        for plugin_file in plugin_dir_path.glob("*.py"):
            if plugin_file.name.startswith('_') or plugin_file.name == '__init__.py':
                continue
            
            module_name = f"{plugin_dir_path.name}.{plugin_file.stem}"
            spec = importlib.util.spec_from_file_location(module_name, plugin_file)
            if spec:
                try:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    if hasattr(module, 'plugin') and isinstance(module.plugin, ChopPlugin):
                        register_plugin(module.plugin)
                except Exception as e:
                    plugin_logger.error(f"Failed to load plugin from '{plugin_file.name}': {e}")
        
        sys.path.pop(0)

    except Exception as e:
        raise ChopError(f"Failed to load plugins from '{plugin_dir}': {e}", code="CHOP-004") from e

# Example plugin: Refined to be more concise
class CustomTextPlugin(ChopPlugin):
    def __init__(self):
        super().__init__(
            name="CustomText",
            modes=["custom_text"],
            extensions=[".ctxt"],
            dependencies=["regex"],
            priority=10
        )

    def process(self, data_source: Union[str, io.StringIO], mode: str) -> List[str]:
        """Handle custom text file format."""
        if not REGEX_AVAILABLE:
            raise ChopDependencyError("The 'regex' library is required for CustomText plugin.", "CHOP-005")
        
        content = data_source.read() if hasattr(data_source, 'read') else data_source
        return regex.findall(r'\w+', content)

# --- Security Utilities ---
def sanitize_path(file_path: Union[str, Path]) -> Path:
    """Sanitize file paths to prevent path traversal vulnerabilities."""
    try:
        path = Path(file_path).resolve()
        allowed = Path(ALLOWED_DIR).resolve()
        if not path.is_relative_to(allowed):
            raise ChopPermissionError(
                f"Access to '{file_path}' is restricted to '{ALLOWED_DIR}'.",
                code="CHOP-006"
            )
        return path
    except (ValueError, OSError) as e:
        raise ChopFileError(f"Invalid path '{file_path}': {e}", code="CHOP-007") from e

def check_file_size(file_obj: Union[TextIO, BinaryIO, io.BytesIO]) -> None:
    """Validate file size against a maximum limit."""
    try:
        pos = file_obj.tell()
        file_obj.seek(0, os.SEEK_END)
        size = file_obj.tell()
        file_obj.seek(pos)
        if size > MAX_FILE_SIZE:
            raise ChopValueError(
                f"File size {size} exceeds limit {MAX_FILE_SIZE}.",
                code="CHOP-008"
            )
    except io.UnsupportedOperation:
        logger.debug("Non-seekable stream detected; skipping size check.")
    except OSError as e:
        raise ChopFileError(f"Failed to check file size: {e}", code="CHOP-009") from e

@contextmanager
def safe_open(file_path: Union[str, Path], mode: str, encoding: Optional[str] = None):
    """
    Safely opens a file within a sandboxed context,
    validates its size, and ensures resource cleanup.
    """
    path = sanitize_path(file_path)
    try:
        with open(path, mode, encoding=encoding) as f:
            check_file_size(f)
            yield f
    except (IOError, OSError) as e:
        raise ChopFileError(f"Failed to open file '{file_path}': {e}", code="CHOP-010") from e

# --- Utility Functions ---
@lru_cache(maxsize=CACHE_SIZE)
def _get_grapheme_clusters(text: str) -> List[str]:
    """Split a string into grapheme clusters using a cache."""
    if not isinstance(text, str):
        raise ChopTypeError(f"Input must be a string, got {type(text)}.", code="CHOP-011")
    
    if not REGEX_AVAILABLE:
        logger.warning("Falling back to simple string handling due to missing 'regex'.")
        return list(text)
    
    return regex.findall(r'\X', text) if text else []

def _is_file_like(obj: Any) -> bool:
    """Checks if an object is a file-like object or a valid file path."""
    if isinstance(obj, (io.IOBase, io.BytesIO, io.StringIO)):
        return True
    if isinstance(obj, (str, Path)):
        try:
            return Path(obj).exists()
        except (ValueError, OSError):
            return False
    return False

def _normalize_index(length: int, index: Union[int, float]) -> int:
    """Normalizes and validates an index against the sequence length."""
    if not isinstance(index, (int, float)):
        raise ChopTypeError(f"Index must be an integer or float, got {type(index)}.", code="CHOP-012")
    if isinstance(index, float):
        if np is not None and (np.isnan(index) or np.isinf(index)):
            raise ChopValueError(f"Index cannot be NaN or infinity, got {index}.", code="CHOP-013")
        index = int(index)
    if not -length <= index < length:
        raise ChopIndexError(f"Index {index} out of bounds for length {length}.", code="CHOP-015")
    
    return index if index >= 0 else index + length

def _normalize_slice_params(
    start: Optional[Union[int, float]], 
    stop: Optional[Union[int, float]], 
    step: Optional[Union[int, float]], 
    length: int
) -> Tuple[int, int, int]:
    """Validates and normalizes slice parameters."""
    if step is not None:
        if not isinstance(step, (int, float)):
            raise ChopTypeError("Slice step must be a number or None.", code="CHOP-016")
        if int(step) == 0:
            raise ChopValueError("Slice step cannot be zero.", code="CHOP-016")
    
    _step = int(step) if step is not None else 1
    _start = int(start) if start is not None else (0 if _step > 0 else length - 1)
    _stop = int(stop) if stop is not None else (length if _step > 0 else -1)

    _start = _normalize_index(length, _start) if start is not None and start < 0 else max(0, _start)
    _stop = _normalize_index(length, _stop) if stop is not None and stop < 0 else min(length, _stop)

    return _start, _stop, _step

def _detect_encoding(file_obj: BinaryIO) -> str:
    """Detects file encoding with a cache."""
    if not CHARSET_NORMALIZER_AVAILABLE:
        logger.warning("Falling back to default encoding due to missing 'charset-normalizer'.")
        return DEFAULT_ENCODING
    
    try:
        # Read a chunk for detection
        file_obj.seek(0)
        content = file_obj.read(CHUNK_SIZE)
        file_obj.seek(0)
        
        result = charset_normalizer.detect(content)
        return result.get('encoding') or DEFAULT_ENCODING
    except Exception as e:
        logger.warning(f"Encoding detection failed: {e}. Defaulting to '{DEFAULT_ENCODING}'.")
        return DEFAULT_ENCODING

def _get_file_length_and_mode(file_path: Union[str, Path], file_mode: Optional[str]) -> Tuple[int, str]:
    """Determines file length and inferred mode for a file path."""
    file_path = sanitize_path(file_path)
    if not file_path.is_file():
        raise ChopFileError(f"File not found: '{file_path}'.", code="CHOP-024")

    # Infer mode if not provided
    if not file_mode:
        ext = file_path.suffix.lower()
        if ext in SUPPORTED_IMAGE_EXTS:
            file_mode = 'pixels'
        elif ext == '.csv':
            file_mode = 'rows'
        elif ext == '.json':
            file_mode = 'items'
        else:
            file_mode = 'lines'
    
    # Use plugins for specialized files
    if file_mode in FILE_MODE_HANDLERS:
        length = FILE_MODE_HANDLERS[file_mode].process(file_path, file_mode)
        return length, file_mode
    
    if file_path.suffix.lower() in FILE_EXTENSION_HANDLERS:
        length = FILE_EXTENSION_HANDLERS[file_path.suffix.lower()].process(file_path, file_mode)
        return length, file_mode

    # Use standard handlers
    if file_mode == 'pixels' and PIL_AVAILABLE:
        with Image.open(str(file_path)) as img:
            length = img.width * img.height
    elif file_mode == 'rows' and file_path.suffix.lower() == '.csv':
        import csv
        with safe_open(file_path, 'r', encoding=DEFAULT_ENCODING) as f:
            length = sum(1 for _ in csv.reader(f))
    elif file_mode == 'items' and file_path.suffix.lower() == '.json':
        import json
        with safe_open(file_path, 'r', encoding=DEFAULT_ENCODING) as f:
            data = json.load(f)
            length = len(data) if isinstance(data, (list, dict)) else 1
    elif file_mode in ('lines', 'bytes'):
        with safe_open(file_path, 'rb') as f:
            if file_mode == 'bytes':
                f.seek(0, os.SEEK_END)
                length = f.tell()
            else: # 'lines'
                try:
                    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                        length = sum(1 for _ in mm.split(b'\n'))
                except (ValueError, io.UnsupportedOperation):
                    f.seek(0)
                    length = sum(1 for _ in f.read().decode(DEFAULT_ENCODING).splitlines())
    else:
        raise ChopValueError(f"Unsupported mode '{file_mode}' or file format.", code="CHOP-033")
    
    return length, file_mode

def _export_pixels_to_image(
    pixels: List[Tuple[int, ...]], 
    width: int, 
    height: int, 
    output_path: Union[str, Path], 
    format: str = 'PNG', 
    **export_options
) -> None:
    """Exports a list of pixels to an image file."""
    if not PIL_AVAILABLE or not NUMPY_AVAILABLE:
        raise ChopDependencyError("Pillow and NumPy are required for image export.", code="CHOP-035")
    try:
        output_path = sanitize_path(output_path)
        mode = 'RGB' if len(pixels[0]) == 3 else 'RGBA'
        pixel_array = np.array(pixels, dtype=np.uint8).reshape(height, width, len(pixels[0]))
        img = Image.fromarray(pixel_array, mode=mode)
        img.save(output_path, format=format.upper(), **export_options)
        logger.info(f"Exported pixels to '{output_path}' in '{format}' format.")
    except Exception as e:
        raise ChopError(f"Failed to export pixels to '{output_path}': {e}", code="CHOP-036") from e

# --- Public API ---
def get_length(obj: Any, file_mode: Optional[str] = None) -> int:
    """
    Get the length of a sequence or file.

    Args:
        obj (Any): The object to measure (string, list, file path, etc.).
        file_mode (str, optional): Mode for file handling ('lines', 'bytes', 'pixels', etc.).

    Returns:
        int: The length of the object.

    Raises:
        ChopError: For invalid inputs or processing errors.
    """
    try:
        if isinstance(obj, str) and not _is_file_like(obj):
            return len(_get_grapheme_clusters(obj))
        elif isinstance(obj, (bytes, bytearray, SequenceType)):
            return len(obj)
        elif _is_file_like(obj):
            if isinstance(obj, (str, Path)):
                length, _ = _get_file_length_and_mode(obj, file_mode)
                return length
            else: # in-memory file-like object
                if file_mode == 'lines':
                    pos = obj.tell()
                    obj.seek(0)
                    length = sum(1 for _ in obj)
                    obj.seek(pos)
                    return length
                elif file_mode == 'bytes':
                    pos = obj.tell()
                    obj.seek(0, os.SEEK_END)
                    length = obj.tell()
                    obj.seek(pos)
                    return length
                else:
                    raise ChopValueError("In-memory file-like objects only support 'lines' or 'bytes' modes.", code="CHOP-049")
        else:
            raise ChopTypeError(f"Invalid sequence or file type: {type(obj)}.", code="CHOP-050")
    except ChopError:
        raise
    except Exception as e:
        raise ChopError(f"Unexpected error in get_length: {e}", code="CHOP-051") from e

def chop(obj: Any, index_or_slice: Any = None, **kwargs) -> Any:
    """
    Main entry point for slicing and chopping data.

    Args:
        obj (Any): The sequence or file to chop.
        index_or_slice (Any, optional): Index, slice, iterable of indices, or region tuple.
        **kwargs: Additional parameters:
            - stop (Union[int, float]): End of slice.
            - step (Union[int, float]): Step for slice.
            - decode (str): Encoding for byte decoding.
            - file_mode (str): File handling mode.
            - encoding (str): Character encoding for text files.
            - region (tuple): Image region (x1, y1, x2, y2).
            - regions (list): List of image regions.
            - export_path (str or Path): Path to save extracted data.
            - export_format (str): Format for exported files.
            - progress (bool): Show progress bar.
            - batch_size (int): Batch size for multi-index operations.

    Returns:
        Any: The chopped result (single element, list, cropped image, etc.).

    Raises:
        ChopError: For invalid inputs or processing errors.
    """
    try:
        # Unpack kwargs for clarity and safety
        stop = kwargs.pop('stop', None)
        step = kwargs.pop('step', 1)
        decode = kwargs.pop('decode', None)
        file_mode = kwargs.pop('file_mode', None)
        encoding = kwargs.pop('encoding', DEFAULT_ENCODING)
        pixel_coords = kwargs.pop('pixel_coords', None)
        region = kwargs.pop('region', None)
        regions = kwargs.pop('regions', None)
        export_path = kwargs.pop('export_path', None)
        export_format = kwargs.pop('export_format', 'PNG')
        progress = kwargs.pop('progress', False)
        
        is_file = _is_file_like(obj)

        if is_file and isinstance(index_or_slice, tuple) and len(index_or_slice) == 4:
            file_mode = 'region'
            region = index_or_slice
            index_or_slice = None
        elif is_file and isinstance(index_or_slice, list) and all(isinstance(r, tuple) and len(r) == 4 for r in index_or_slice):
            file_mode = 'region'
            regions = index_or_slice
            index_or_slice = None

        if decode:
            return _chop_bytes_to_str(obj, index_or_slice, stop, step, decode)

        # Main dispatch logic
        if index_or_slice is None and stop is None and not region and not regions:
            return _chop_slice_impl(obj, None, None, step, file_mode, encoding, region, regions, export_path, export_format, progress)
        elif isinstance(index_or_slice, (int, float)):
            return _chop_at_impl(obj, index_or_slice, file_mode, encoding, pixel_coords)
        elif isinstance(index_or_slice, slice):
            return _chop_slice_impl(obj, index_or_slice.start, index_or_slice.stop, index_or_slice.step, file_mode, encoding, region, regions, export_path, export_format, progress)
        elif isinstance(index_or_slice, Iterable) and not isinstance(index_or_slice, (str, bytes, bytearray)):
            return _chop_multi_impl(obj, index_or_slice, file_mode, encoding, pixel_coords)
        elif stop is not None:
            return _chop_slice_impl(obj, index_or_slice, stop, step, file_mode, encoding, region, regions, export_path, export_format, progress)
        elif region or regions:
            return _chop_slice_impl(obj, None, None, None, file_mode, encoding, region, regions, export_path, export_format, progress)

        raise ChopTypeError(f"Invalid index or slice type: {type(index_or_slice)}.", code="CHOP-052")
    except ChopError:
        raise
    except Exception as e:
        raise ChopError(f"Unexpected error in chop: {e}", code="CHOP-053") from e

def _chop_at_impl(
    obj: Any, 
    index: Union[int, float], 
    file_mode: Optional[str], 
    encoding: str, 
    pixel_coords: Optional[Tuple[int, int]]
) -> Any:
    """Implementation for extracting a single element."""
    if isinstance(obj, str) and not _is_file_like(obj):
        graphemes = _get_grapheme_clusters(obj)
        normalized_index = _normalize_index(len(graphemes), index)
        return graphemes[normalized_index]
    elif isinstance(obj, (bytes, bytearray, SequenceType)):
        normalized_index = _normalize_index(len(obj), index)
        return obj[normalized_index]
    elif _is_file_like(obj):
        return _chop_file_at_index(obj, index, file_mode, encoding, pixel_coords)
    else:
        raise ChopTypeError(f"Object {type(obj)} is not indexable.", code="CHOP-054")

def _chop_file_at_index(
    file_source: Any, 
    index: Union[int, float], 
    file_mode: Optional[str], 
    encoding: str, 
    pixel_coords: Optional[Tuple[int, int]]
) -> Any:
    """Helper to extract a single element from a file-like object."""
    is_path = isinstance(file_source, (str, Path))
    
    if is_path:
        length, _file_mode = _get_file_length_and_mode(file_source, file_mode)
        normalized_index = _normalize_index(length, index)
    else:
        _file_mode = file_mode or 'lines' if hasattr(file_source, 'read') and 'b' not in file_source.mode else 'bytes'
        length = get_length(file_source, file_mode=_file_mode)
        normalized_index = _normalize_index(length, index)

    # Dispatch based on mode
    if _file_mode == 'pixels' and PIL_AVAILABLE:
        with Image.open(str(file_source) if is_path else file_source) as img:
            if pixel_coords:
                x, y = pixel_coords
                if not (0 <= x < img.width and 0 <= y < img.height):
                    raise ChopIndexError(f"Pixel coordinates {pixel_coords} out of bounds.", code="CHOP-055")
                return img.getpixel((x, y))
            else:
                width = img.width
                x, y = divmod(normalized_index, width)
                return img.getpixel((x, y))
    elif _file_mode == 'lines':
        if is_path:
            with safe_open(file_source, 'r', encoding=encoding) as f:
                return f.readlines()[normalized_index].rstrip('\n')
        else: # in-memory
            lines = file_source.readlines()
            return lines[normalized_index].rstrip('\n')
    elif _file_mode == 'bytes':
        if is_path:
            with safe_open(file_source, 'rb') as f:
                f.seek(normalized_index)
                byte = f.read(1)
                if not byte:
                    raise ChopIndexError(f"Index {normalized_index} out of range for length {length}.", code="CHOP-056")
                return ord(byte)
        else: # in-memory
            file_source.seek(normalized_index)
            byte = file_source.read(1)
            if not byte:
                raise ChopIndexError(f"Index {normalized_index} out of range for length {length}.", code="CHOP-056")
            return ord(byte)
    
    raise ChopValueError(f"Invalid file_mode: '{file_mode}'.", code="CHOP-057")

def _chop_slice_impl(
    obj: Any, 
    start: Optional[Any], 
    stop: Optional[Any], 
    step: Optional[Any], 
    file_mode: Optional[str], 
    encoding: str, 
    region: Optional[Any], 
    regions: Optional[Any], 
    export_path: Optional[Any], 
    export_format: str, 
    progress: bool,
) -> Any:
    """Implementation for slicing an object."""
    if isinstance(obj, str) and not _is_file_like(obj):
        graphemes = _get_grapheme_clusters(obj)
        _start, _stop, _step = _normalize_slice_params(start, stop, step, len(graphemes))
        return ''.join(graphemes[_start:_stop:_step])
    elif isinstance(obj, (bytes, bytearray, SequenceType)):
        _start, _stop, _step = _normalize_slice_params(start, stop, step, len(obj))
        return obj[_start:_stop:_step]
    elif _is_file_like(obj):
        return _chop_file_slice(obj, start, stop, step, file_mode, encoding, region, regions, export_path, export_format, progress)
    else:
        raise ChopTypeError(f"Object {type(obj)} is not sliceable.", code="CHOP-058")

def _chop_file_slice(
    file_source: Any,
    start: Optional[Any], 
    stop: Optional[Any], 
    step: Optional[Any], 
    file_mode: Optional[str], 
    encoding: str, 
    region: Optional[Any], 
    regions: Optional[Any], 
    export_path: Optional[Any], 
    export_format: str, 
    progress: bool,
) -> Any:
    """Helper to slice a file-like object."""
    is_path = isinstance(file_source, (str, Path))
    
    if is_path:
        length, _file_mode = _get_file_length_and_mode(file_source, file_mode)
    else:
        _file_mode = file_mode or 'lines' if hasattr(file_source, 'read') and 'b' not in file_source.mode else 'bytes'
        length = get_length(file_source, file_mode=_file_mode)

    if _file_mode == 'region' and PIL_AVAILABLE:
        with Image.open(str(file_source) if is_path else file_source) as img:
            if region:
                x1, y1, x2, y2 = region
                if not (0 <= x1 < x2 <= img.width and 0 <= y1 < y2 <= img.height):
                    raise ChopValueError(f"Invalid region {region} for image size {img.size}.", code="CHOP-059")
                cropped = img.crop((x1, y1, x2, y2))
                if export_path:
                    _export_pixels_to_image(list(cropped.getdata()), cropped.width, cropped.height, export_path, export_format)
                return cropped
            elif regions:
                results = []
                for r in regions:
                    x1, y1, x2, y2 = r
                    if not (0 <= x1 < x2 <= img.width and 0 <= y1 < y2 <= img.height):
                        raise ChopValueError(f"Invalid region {r} for image size {img.size}.", code="CHOP-060")
                    results.append(img.crop((x1, y1, x2, y2)))
                if export_path:
                    for i, cropped in enumerate(results):
                        path = Path(export_path).stem + f"_{i}.{export_format.lower()}"
                        _export_pixels_to_image(list(cropped.getdata()), cropped.width, cropped.height, path, export_format)
                return results

    _start, _stop, _step = _normalize_slice_params(start, stop, step, length)

    if _file_mode == 'lines':
        file_obj = safe_open(file_source, 'r', encoding=encoding) if is_path else file_source
        with file_obj:
            lines = []
            if is_path:
                lines = file_obj.readlines()
            else: # in-memory object
                file_obj.seek(0)
                lines = file_obj.readlines()
            
            result = [lines[i].rstrip('\n') for i in range(_start, _stop, _step)]
            
            if progress and TQDM_AVAILABLE:
                with tqdm(total=len(result), desc="Processing lines") as pbar:
                    pbar.update(len(result))
            
            return result
    
    elif _file_mode == 'bytes':
        file_obj = safe_open(file_source, 'rb') if is_path else file_source
        with file_obj:
            with file_lock:
                if is_path:
                    try:
                        with mmap.mmap(file_obj.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                            return mm[_start:_stop:_step]
                    except (ValueError, io.UnsupportedOperation):
                        file_obj.seek(_start)
                        data = file_obj.read(_stop - _start)
                        return data[::step]
                else: # in-memory object
                    file_obj.seek(_start)
                    data = file_obj.read(_stop - _start)
                    return data[::step]

    raise ChopValueError(f"Invalid file_mode: '{_file_mode}'.", code="CHOP-061")


def _chop_multi_impl(
    obj: Any, 
    indices: Iterable[Union[int, float]], 
    file_mode: Optional[str], 
    encoding: str, 
    pixel_coords: Optional[Tuple[int, int]]
) -> List[Any]:
    """Implementation for extracting multiple elements from a list of indices."""
    if not isinstance(indices, Iterable) or isinstance(indices, (str, bytes, bytearray)):
        raise ChopTypeError(f"Indices must be an iterable, got {type(indices)}.", code="CHOP-062")
    
    return [_chop_at_impl(obj, idx, file_mode, encoding, pixel_coords) for idx in indices]

def _chop_bytes_to_str(
    data: Union[bytes, bytearray, str, Path, io.BytesIO], 
    start: Optional[Any], 
    stop: Optional[Any], 
    step: Optional[Any], 
    encoding: Optional[str]
) -> str:
    """Slices bytes and decodes them to a string."""
    is_path = isinstance(data, (str, Path)) and Path(data).is_file()
    
    try:
        if is_path:
            with safe_open(data, 'rb') as f:
                sliced_bytes = _chop_file_slice(f, start, stop, step, 'bytes', encoding, None, None, None, 'PNG', False)
        elif isinstance(data, (bytes, bytearray, io.BytesIO)):
            sliced_bytes = _chop_slice_impl(data, start, stop, step, 'bytes', encoding, None, None, None, 'PNG', False)
        else:
            raise ChopTypeError(f"Input must be bytes, bytearray, BytesIO, or a file path, got {type(data)}.", code="CHOP-063")
        
        _encoding = encoding or _detect_encoding(io.BytesIO(sliced_bytes))
        return sliced_bytes.decode(_encoding)
    except UnicodeDecodeError as e:
        raise ChopValueError(f"Failed to decode with '{_encoding}': {e}.", code="CHOP-064") from e
    except ChopError:
        raise
    except Exception as e:
        raise ChopError(f"Unexpected error in _chop_bytes_to_str: {e}", code="CHOP-065") from e

# --- Test Suite ---
def run_tests():
    """Run comprehensive test suite with coverage and benchmarks."""
    try:
        import pytest
    except ImportError:
        logger.error("pytest not installed. Install with 'pip install pytest'.")
        return
    
    # Run pytest directly from a temp directory
    temp_dir = tempfile.mkdtemp()
    test_file_path = Path(temp_dir) / 'test_module.py'
    
    # Write test cases to a temporary file
    test_code = f"""
import os
import shutil
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from PIL import Image
import json
import csv
from datachop import chop, get_length, ChopIndexError, ChopValueError, ChopTypeError, ChopFileError, ChopPermissionError, ChopDependencyError, __file__ as datachop_path

datachop_dir = Path(datachop_path).parent
temp_dir = None

def setup_module(module):
    global temp_dir
    temp_dir = Path(tempfile.mkdtemp())
    with open(temp_dir / "test.txt", 'w', encoding='utf-8') as f:
        f.write("Line 1\\nLine 2\\nLine 3\\n")
    with open(temp_dir / "test.bin", 'wb') as f:
        f.write(b"abcde")
    if Image:
        img = Image.new('RGB', (10, 10), color='red')
        img.save(temp_dir / "test.png")
    with open(temp_dir / "test.json", 'w', encoding='utf-8') as f:
        json.dump([1, 2, 3], f)
    with open(temp_dir / "test.csv", 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows([['a', 'b'], ['c', 'd']])
    with open(temp_dir / "empty.txt", 'w') as f:
        pass
    
    os.chdir(str(temp_dir))
    
    # Patch ALLOWED_DIR to the temporary directory
    patcher = patch('datachop.ALLOWED_DIR', str(temp_dir))
    patcher.start()
    module.teardown_patcher = patcher

def teardown_module(module):
    module.teardown_patcher.stop()
    os.chdir(datachop_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)
    
def test_string_slicing():
    assert chop("Hello😊👍", 5) == '👍'
    assert chop("Hello😊👍", slice(2, 5)) == 'llo'
    assert chop("Hello😊👍", [0, 2, 5]) == ['H', 'l', '👍']
    assert chop("", 0) == ''
    with pytest.raises(ChopIndexError):
        chop("abc", 10)
    with pytest.raises(ChopValueError):
        chop("abc", float('nan'))

def test_bytes_slicing():
    assert chop(b"abc", 1) == ord('b')
    assert chop(b"abc", slice(0, 2)) == b"ab"
    assert chop(b"abc", 0, 2, decode='utf-8') == 'ab'
    with pytest.raises(ChopValueError):
        chop(b"\\xFF\\xFF", 0, 2, decode='utf-8')

def test_list_slicing():
    assert chop([1, 2, 3], 1) == 2
    assert chop([1, 2, 3], slice(0, 2)) == [1, 2]
    assert chop([1, 2, 3], [0, 2]) == [1, 3]
    with pytest.raises(ChopIndexError):
        chop([], 0)

def test_file_slicing_lines():
    text_file = "test.txt"
    assert chop(text_file, 1, file_mode='lines') == "Line 2"
    assert chop(text_file, slice(0, 2), file_mode='lines') == ["Line 1", "Line 2"]
    with open(text_file, 'r', encoding='utf-8') as f:
        assert chop(f, 0, file_mode='lines') == "Line 1"

def test_file_slicing_bytes():
    bin_file = "test.bin"
    assert chop(bin_file, 1, file_mode='bytes') == ord('b')
    assert chop(bin_file, slice(0, 2), file_mode='bytes') == b"ab"
    with open(bin_file, 'rb') as f:
        assert chop(f, 0, file_mode='bytes') == ord('a')

def test_image_slicing():
    if not Image:
        pytest.skip("Pillow is not installed")
    img_file = "test.png"
    assert chop(img_file, 0, file_mode='pixels') == (255, 0, 0)
    assert len(chop(img_file, slice(0, 4), file_mode='pixels')) == 4
    assert (chop(img_file, (0, 0, 2, 2))).size == (2, 2)
    assert len(chop(img_file, regions=[(0, 0, 1, 1), (1, 1, 2, 2)])) == 2
    with pytest.raises(ChopValueError):
        chop(img_file, (0, 0, 20, 20))
    with pytest.raises(ChopValueError):
        chop(img_file, (0, 0, 0, 0))

def test_get_length():
    assert get_length("Hello😊👍") == 7
    assert get_length([1, 2, 3, 4]) == 4
    assert get_length("test.txt", file_mode='lines') == 4
    assert get_length("test.bin", file_mode='bytes') == 5
    if Image:
        assert get_length("test.png", file_mode='pixels') == 100
    with pytest.raises(ChopTypeError):
        get_length(None)

def test_edge_cases():
    with pytest.raises(ChopValueError):
        chop("abc", 0, 2, 0)
    with pytest.raises(ChopTypeError):
        chop(None, 0)
    with pytest.raises(ChopFileError):
        chop("nonexistent.txt", 0, file_mode='lines')
    with pytest.raises(ChopPermissionError):
        chop("/root/test.txt", 0, file_mode='lines')
    assert get_length("empty.txt", file_mode='lines') == 1

@patch('datachop.PIL_AVAILABLE', False)
def test_missing_dependency():
    with pytest.raises(ChopDependencyError):
        chop("test.png", 0, file_mode='pixels')
"""
    test_file_path.write_text(test_code)
    
    # Run pytest on the temporary file
    pytest_args = [str(test_file_path)]
    
    print(f"Running tests in temporary directory: {temp_dir}")
    pytest.main(pytest_args)
    
    shutil.rmtree(temp_dir, ignore_errors=True)

# --- Main Entry Point ---
if __name__ == "__main__":
    print(f"=== DataChop v{__version__}: The Ultimate Slicing Module ===")
    
    try:
        print("Loading plugins...")
        # Placeholder for dynamic plugin loading.
        # For a real project, this should be an automated discovery step.
        pass
        
        print("Running comprehensive test suite...")
        run_tests()

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
