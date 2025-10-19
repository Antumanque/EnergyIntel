"""
Main orchestration module for the API Data Ingestion Template data ingestion service.

This module coordinates the entire workflow:
1. Load configuration
2. Initialize database
3. Fetch data from configured APIs
4. Save raw data to database
5. Report results
"""

import logging
import sys
from typing import Dict, List

from src.client import get_api_client
from src.database import get_database_manager
from src.settings import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class DataIngestionService:
    """
    Main service class that orchestrates the data ingestion workflow.

    It follows a clear, step-by-step process to fetch and store API data.
    """

    def __init__(self):
        """Initialize the service with configuration and dependencies."""
        # Load settings
        self.settings = get_settings()
        logger.info("Settings loaded successfully")

        # Initialize dependencies
        self.api_client = get_api_client(self.settings)
        self.db_manager = get_database_manager(self.settings)
        logger.info("Service dependencies initialized")

        # Track results
        self.results: Dict[str, dict] = {}

    def setup_database(self) -> None:
        """
        Set up the database connection and create necessary tables.

        This method is idempotent - it can be called multiple times safely.
        """
        logger.info("Setting up database...")
        try:
            # Ensure we can connect
            self.db_manager.get_connection()

            # Create tables if they don't exist
            self.db_manager.create_tables()

            logger.info("Database setup completed successfully")
        except Exception as e:
            logger.error(f"Database setup failed: {e}")
            raise

    def fetch_and_store_url(self, url: str) -> dict:
        """
        Fetch data from a single URL and store it in the database.

        Args:
            url: The URL to fetch

        Returns:
            Dictionary with fetch results (success, status_code, error, etc.)
        """
        logger.info(f"Processing URL: {url}")

        # Fetch the data
        status_code, data, error = self.api_client.fetch_url(url)

        # Prepare result metadata
        result = {
            "url": url,
            "status_code": status_code,
            "success": error is None,
            "error": error,
        }

        # Store in database
        try:
            row_id = self.db_manager.insert_raw_data(
                source_url=url, status_code=status_code, data=data, error_message=error
            )
            result["row_id"] = row_id
            logger.info(f" Successfully processed {url} (row_id: {row_id})")
        except Exception as e:
            result["success"] = False
            result["error"] = f"Database insert failed: {str(e)}"
            logger.error(f" Failed to store data from {url}: {e}")

        return result

    def process_all_urls(self) -> None:
        """
        Process all configured URLs sequentially.

        This method fetches and stores data from each URL in the configuration.
        Errors for individual URLs don't stop the overall process.
        """
        urls = self.settings.api_urls

        if not urls:
            logger.warning(
                "No API URLs configured. Please set API_URLS environment variable."
            )
            return

        logger.info(f"Processing {len(urls)} URL(s)...")

        for url in urls:
            result = self.fetch_and_store_url(url)
            self.results[url] = result

        logger.info("All URLs processed")

    def print_summary(self) -> None:
        """
        Print a summary of the ingestion results.

        This provides a clear overview of what succeeded and what failed.
        """
        if not self.results:
            logger.info("No results to summarize")
            return

        total = len(self.results)
        successful = sum(1 for r in self.results.values() if r["success"])
        failed = total - successful

        logger.info("=" * 60)
        logger.info("INGESTION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total URLs processed: {total}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")

        if failed > 0:
            logger.info("\nFailed URLs:")
            for url, result in self.results.items():
                if not result["success"]:
                    logger.info(f"  - {url}")
                    logger.info(f"    Error: {result['error']}")

        logger.info("=" * 60)

    def run(self) -> int:
        """
        Run the complete data ingestion workflow.

        Returns:
            Exit code (0 for success, 1 for failure)
        """
        try:
            logger.info("Starting API Data Ingestion Template data ingestion service...")

            # Step 1: Set up database
            self.setup_database()

            # Step 2: Process all URLs
            self.process_all_urls()

            # Step 3: Print summary
            self.print_summary()

            # Determine exit code based on results
            if not self.results:
                logger.warning("No data was processed")
                return 1

            # Exit with error if ALL requests failed
            all_failed = all(not r["success"] for r in self.results.values())
            if all_failed:
                logger.error("All requests failed")
                return 1

            logger.info("Data ingestion completed successfully")
            return 0

        except Exception as e:
            logger.error(f"Fatal error during ingestion: {e}", exc_info=True)
            return 1

        finally:
            # Always clean up resources
            try:
                self.db_manager.close_connection()
                logger.info("Resources cleaned up")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")


def main() -> None:
    """
    Main entry point for the application.

    This function is called when the module is run directly.
    """
    service = DataIngestionService()
    exit_code = service.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
