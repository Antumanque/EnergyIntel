"""
Clase base para repositorios de base de datos.

Este módulo define la interfaz base para repositorios que interactúan con la BD.
"""

import logging
from typing import Any

from src.core.database import DatabaseManager

logger = logging.getLogger(__name__)


class BaseRepository:
    """
    Clase base para repositorios de base de datos.

    Provee funcionalidad común para todos los repositorios.
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Inicializar el repositorio con un gestor de base de datos.

        Args:
            db_manager: Instancia de DatabaseManager
        """
        self.db = db_manager

    def begin_transaction(self) -> None:
        """Iniciar una transacción."""
        self.db.execute_query("START TRANSACTION")

    def commit_transaction(self) -> None:
        """Hacer commit de la transacción actual."""
        self.db.get_connection().commit()

    def rollback_transaction(self) -> None:
        """Hacer rollback de la transacción actual."""
        self.db.get_connection().rollback()
