"""
Transformers module for normalizing raw API data.

This module contains transformer functions for converting raw JSON data
into normalized database tables.
"""

from src.transformers.interesados import transform_interesados

__all__ = ["transform_interesados"]
