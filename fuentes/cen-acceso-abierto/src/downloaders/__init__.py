"""
Módulo de descarga de documentos.

Este módulo maneja la descarga de archivos desde URLs remotas (S3, HTTP, etc.)
hacia almacenamiento local.
"""

from .documents import DocumentDownloader

__all__ = ["DocumentDownloader"]
