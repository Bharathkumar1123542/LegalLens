"""
File Validation — LegalLens Phase 8
Enhanced security validation for file uploads beyond basic magic-byte checks.
Implements: architecture.md §10 Security Mitigations
"""

import io
import logging
import magic
from typing import Optional, Tuple

from fastapi import UploadFile, HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

# Maximum file sizes (defense in depth)
MAX_PDF_SIZE_MB = 50      # PDFs can be large for multi-page documents
MAX_DOCX_SIZE_MB = 25     # DOCX typically smaller
MAX_TEXT_SIZE_MB = 10     # Plain text should be small
MAX_UPLOAD_SIZE_MB = settings.MAX_UPLOAD_SIZE_MB  # Global maximum

# Allowed MIME types (per architecture.md §7.3)
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

# File extension to MIME type mapping (for cross-validation)
EXTENSION_TO_MIME = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}

# Dangerous file patterns (additional security checks)
DANGEROUS_PATTERNS = [
    b"<script",           # JavaScript in files
    b"<?php",             # PHP code
    b"#!/bin/bash",       # Shell scripts
    b"#!/usr/bin/python", # Python scripts
    b"\x4d\x5a",          # PE executable (MZ header)
    b"\x7f\x45\x4c\x46",  # ELF executable
]


class FileValidationError(Exception):
    """Raised when file validation fails."""
    pass


def validate_file_size(file_bytes: bytes, mime_type: str) -> None:
    """
    Validate file size against type-specific limits.
    
    Args:
        file_bytes: File content
        mime_type: Detected MIME type
    
    Raises:
        FileValidationError: If file too large
    """
    size_mb = len(file_bytes) / (1024 * 1024)
    
    # Global maximum
    if size_mb > MAX_UPLOAD_SIZE_MB:
        raise FileValidationError(
            f"File too large: {size_mb:.1f}MB exceeds global limit of {MAX_UPLOAD_SIZE_MB}MB"
        )
    
    # Type-specific limits
    if mime_type == "application/pdf" and size_mb > MAX_PDF_SIZE_MB:
        raise FileValidationError(f"PDF too large: {size_mb:.1f}MB exceeds {MAX_PDF_SIZE_MB}MB limit")
    
    if mime_type.endswith("wordprocessingml.document") and size_mb > MAX_DOCX_SIZE_MB:
        raise FileValidationError(f"DOCX too large: {size_mb:.1f}MB exceeds {MAX_DOCX_SIZE_MB}MB limit")
    
    if mime_type == "text/plain" and size_mb > MAX_TEXT_SIZE_MB:
        raise FileValidationError(f"Text file too large: {size_mb:.1f}MB exceeds {MAX_TEXT_SIZE_MB}MB limit")
    
    logger.info(f"File size validation passed: {size_mb:.2f}MB ({mime_type})")


def detect_mime_type_strict(file_bytes: bytes, filename: str) -> str:
    """
    Strict MIME type detection using python-magic (libmagic).
    
    Per code-standards.md: "Files validated by magic-byte inspection, NOT extension"
    
    Args:
        file_bytes: File content
        filename: Original filename (for extension cross-check)
    
    Returns:
        Detected MIME type
    
    Raises:
        FileValidationError: If type not allowed or mismatch detected
    """
    # Detect using libmagic (most reliable)
    try:
        detected_mime = magic.from_buffer(file_bytes, mime=True)
    except Exception as e:
        logger.error(f"Magic-byte detection failed: {e}")
        raise FileValidationError("Unable to determine file type")
    
    # Normalize MIME types (magic sometimes returns variations)
    if detected_mime == "application/zip":
        # Check if it's actually a DOCX (DOCX is a ZIP container)
        if b"word/" in file_bytes[:2048]:  # DOCX has word/ in ZIP structure
            detected_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    
    # Check if allowed
    if detected_mime not in ALLOWED_MIME_TYPES:
        logger.warning(f"Unsupported MIME type: {detected_mime} for file {filename}")
        raise FileValidationError(
            f"Unsupported file type: {detected_mime}. "
            f"Only PDF, DOCX, and TXT files are allowed."
        )
    
    # Cross-validate with file extension (detect disguised files)
    file_ext = filename.lower().split(".")[-1] if "." in filename else ""
    file_ext_full = f".{file_ext}"
    
    if file_ext_full in EXTENSION_TO_MIME:
        expected_mime = EXTENSION_TO_MIME[file_ext_full]
        if detected_mime != expected_mime:
            logger.warning(
                f"MIME type mismatch: file={filename}, "
                f"extension_expects={expected_mime}, detected={detected_mime}"
            )
            raise FileValidationError(
                f"File type mismatch: .{file_ext} files should be {expected_mime}, "
                f"but file appears to be {detected_mime}"
            )
    
    logger.info(f"MIME type validated: {detected_mime} for {filename}")
    return detected_mime


def check_dangerous_patterns(file_bytes: bytes, filename: str) -> None:
    """
    Check for dangerous patterns in file content.
    
    Args:
        file_bytes: File content
        filename: Original filename
    
    Raises:
        FileValidationError: If dangerous content detected
    """
    # Check first 8KB for dangerous patterns (enough to catch headers)
    sample = file_bytes[:8192]
    
    for pattern in DANGEROUS_PATTERNS:
        if pattern in sample:
            logger.error(f"Dangerous pattern detected in {filename}: {pattern[:20]}")
            raise FileValidationError(
                "File contains suspicious content and cannot be accepted"
            )
    
    # Check for null bytes in text files (binary content)
    if b"\x00" in sample and "text" in filename.lower():
        logger.warning(f"Null bytes detected in text file: {filename}")
        raise FileValidationError("Text file contains binary content")
    
    logger.debug(f"Dangerous pattern check passed for {filename}")


def validate_pdf_structure(file_bytes: bytes) -> None:
    """
    Basic PDF structure validation.
    
    Args:
        file_bytes: PDF file content
    
    Raises:
        FileValidationError: If PDF structure invalid
    """
    # PDF must start with %PDF-
    if not file_bytes.startswith(b"%PDF-"):
        raise FileValidationError("Invalid PDF: missing PDF header")
    
    # PDF should contain %%EOF near end (within last 1KB)
    if b"%%EOF" not in file_bytes[-1024:]:
        logger.warning("PDF missing EOF marker (may be truncated or corrupted)")
        # Don't raise - some PDFs lack EOF marker but are still valid
    
    # Check for PDF version
    header = file_bytes[:20].decode("latin-1", errors="ignore")
    if "%PDF-" in header:
        version = header.split("%PDF-")[1][:3]
        logger.info(f"PDF version: {version}")
    
    logger.debug("PDF structure validation passed")


def validate_docx_structure(file_bytes: bytes) -> None:
    """
    Basic DOCX structure validation (ZIP-based).
    
    Args:
        file_bytes: DOCX file content
    
    Raises:
        FileValidationError: If DOCX structure invalid
    """
    # DOCX must start with ZIP signature (PK)
    if not file_bytes.startswith(b"PK\x03\x04"):
        raise FileValidationError("Invalid DOCX: missing ZIP signature")
    
    # Should contain word/ directory markers
    if b"word/" not in file_bytes[:4096]:
        raise FileValidationError(
            "Invalid DOCX: missing Word document structure. "
            "File may be a regular ZIP archive."
        )
    
    # Check for document.xml (core content file)
    if b"word/document.xml" not in file_bytes[:8192]:
        logger.warning("DOCX missing document.xml reference")
    
    logger.debug("DOCX structure validation passed")


async def validate_upload_comprehensive(
    file: UploadFile,
    max_size_mb: Optional[int] = None,
) -> Tuple[bytes, str]:
    """
    Comprehensive file validation with all security checks.
    
    This is the main entry point for upload validation.
    
    Args:
        file: Uploaded file
        max_size_mb: Optional custom size limit
    
    Returns:
        Tuple of (file_bytes, mime_type)
    
    Raises:
        HTTPException: If validation fails (with appropriate status code)
    """
    try:
        # Read file content
        file_bytes = await file.read()
        await file.seek(0)  # Reset for potential re-read
        
        if not file_bytes:
            raise FileValidationError("Empty file uploaded")
        
        filename = file.filename or "unknown"
        
        logger.info(
            f"Validating upload: filename={filename}, "
            f"size={len(file_bytes)} bytes, "
            f"content_type={file.content_type}"
        )
        
        # 1. Strict MIME type detection (magic-byte based)
        mime_type = detect_mime_type_strict(file_bytes, filename)
        
        # 2. File size validation (type-specific limits)
        validate_file_size(file_bytes, mime_type)
        
        # 3. Dangerous pattern detection
        check_dangerous_patterns(file_bytes, filename)
        
        # 4. Format-specific structure validation
        if mime_type == "application/pdf":
            validate_pdf_structure(file_bytes)
        elif mime_type.endswith("wordprocessingml.document"):
            validate_docx_structure(file_bytes)
        
        logger.info(
            f"Upload validation passed: {filename} "
            f"({len(file_bytes)} bytes, {mime_type})"
        )
        
        return file_bytes, mime_type
        
    except FileValidationError as e:
        logger.warning(f"File validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected validation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File validation failed due to internal error",
        )


def get_safe_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks.
    
    Args:
        filename: Original filename
    
    Returns:
        Safe filename (basename only, dangerous chars removed)
    """
    import os
    import re
    
    # Get basename only (no directory traversal)
    safe = os.path.basename(filename)
    
    # Remove dangerous characters
    safe = re.sub(r'[^\w\s\-\.]', '_', safe)
    
    # Limit length
    if len(safe) > 200:
        name, ext = os.path.splitext(safe)
        safe = name[:190] + ext
    
    # Ensure not empty
    if not safe or safe in [".", ".."]:
        safe = "document.pdf"
    
    return safe
