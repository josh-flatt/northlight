import logging
import datetime
import os
import warnings

from northlight.runtime.log_header import build_header


class LoggingClient:
    def __init__(
        self, path: str = "logs", filename: str = "log", base_level: str = "INFO"
    ) -> None:
        """
        Initializes a new instance of the LoggingClient class.

        Configures the logger with the specified parameters
        and initializes the log file.

        Parameters
        ----------
        path : str, optional
            The path to the directory where the
            log files will be stored. Defaults to "logs".
        filename : str, optional
            The base name of the log files. Defaults to "log".
        base_level : str, optional
            The base logging level. Accepts "DEBUG", "INFO",
            "WARNING", "ERROR", and "CRITICAL". Defaults to "INFO".

        Returns
        -------
        None
        """
        # Parameters
        self.path = path
        self.filename = filename
        self.base_level = base_level

        # Logging variables
        self.now = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        self.log_format = "[%(asctime)s] [%(levelname)s] %(msg)s"
        self.full_log_path = f"{self.path}/{self.filename}_{self.now}.log"

        # Create the log directory if it doesn't exist
        if not os.path.isdir(self.path):
            os.mkdir(self.path)

        logging.basicConfig(
            filename=self.full_log_path, format=self.log_format, level=self.base_level
        )

        _header_written = False
        if not _header_written:
            header = build_header()
            self._write_raw(header)
            _header_written = True

    def _write_raw(self, msg: str) -> None:
        """
        Writes a raw message to the log file or prints it to the console.

        Parameters
        ----------
        message :str
            The debug message to be logged.

        Returns
        -------
        None
        """
        if self.full_log_path:
            with open(self.full_log_path, "a") as f:
                f.write(msg + "\n")
        else:
            print(msg)

    def debug(self, message: str) -> None:
        """
        Logs a debug message using the logger instance.

        Parameters
        ----------
        message :str
            The debug message to be logged.

        Returns
        -------
        None
        """
        logging.debug(message)

    def info(self, message: str) -> None:
        """
        Logs an informational message using the logger instance.

        Parameters
        ----------
        message :str
            The informational message to be logged.

        Returns
        -------
        None
        """
        logging.info(message)

    def warning(self, message: str) -> None:
        """
        Logs a warning message using the logger instance.

        Parameters
        ----------
        message :str
            The warning message to be logged.

        Returns
        -------
        None
        """
        logging.warning(message)

    def error(self, message: str) -> None:
        """
        Logs an error message using the logger instance.

        Parameters
        ----------
        message :str
            The error message to be logged.

        Returns
        -------
        None
        """
        logging.error(message)

    def critical(self, message: str) -> None:
        """
        Logs a critical message using the logger instance.

        Parameters
        ----------
        message :str
            The critical message to be logged.

        Returns
        -------
        None
        """
        logging.critical(message)

    def exception(self, message: str | Exception) -> None:
        """
        Logs an exception message using the logger instance.

        Parameters
        ----------
        message : str, Exception
            The exception message to be logged.

        Returns
        -------
        None
        """
        logging.exception(message)

    def close(self) -> None:
        """
        Closes the logger instance and shuts down the logging system.

        This function is used to properly close the logger instance
        and shut down the logging system. It should be called when
        the logging is no longer needed to free up resources and
        ensure proper cleanup.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        logging.shutdown()
