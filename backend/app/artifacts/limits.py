"""Artifact size and shape limits, in one place so they can be tuned later."""

# Paths
MAX_PATH_LENGTH = 255      # characters in a whole relative path
MAX_SEGMENT_LENGTH = 100   # characters in one folder or file name
MAX_PATH_DEPTH = 16        # folders + file name

# Content
MAX_FILES = 200                 # files per artifact
MAX_FILE_BYTES = 1_000_000      # UTF-8 bytes per file
MAX_TOTAL_BYTES = 5_000_000     # UTF-8 bytes across all files of one artifact

# Document export (PDF / TXT)
MAX_EXPORT_CHARS = 2_000_000    # characters of source Markdown accepted for one export
