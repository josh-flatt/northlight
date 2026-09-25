import uopy
import pandas as pd
import logging
import os
import sys
from dotenv import load_dotenv
import uopy._errorcodes
import warnings
import re
from typing import Optional


class UniDataClient:
    def __init__(
        self, hostname: str, username: str, password: str, path: str, port: int
    ):
        """
        Initializes a new instance of the class.

        Parameters
        ----------
        hostname : str
            The hostname of the UniData server.
        username : str
            The username for authentication.
        password : str
            The password for authentication.
        path : str
            The path to connect to.
        port : int
            The port number for the connection.

        Returns
        -------
        None

        Calls the following methods
        ---------------------------
        `__generate_connection()`
            Generates the connection to the database.
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.path = path
        self.port = port
        self.logger = logging.getLogger(__name__)
        self.__generate_connection()

    def __generate_connection(self) -> uopy.Session:
        """
        Generate a connection to the database using the provided credentials and environment variables.

        This method establishes a connection to the database using the `uopy.connect` function.
        It takes the values of the `hostname`, `username`, `password`, `path`, and `port` attributes
        from the `self` object and passes them as arguments to the `uopy.connect` function.
        The resulting session object is assigned to the `self.session` attribute.

        Parameters
        ----------
        None

        Returns
        -------
        uopy.Session
            The session object representing the connection to the database.
        """
        self.session = uopy.connect(
            host=self.hostname,
            user=self.username,
            password=self.password,
            account=self.path,
            port=self.port,
            encoding="iso-8859-1",
        )
        self.cmd = uopy.Command(session=self.session)
        return self.session

    def make_requests(
        self,
        queries: list[str],
        clear_selects: bool = True,
        stop_on_error: bool = True,
    ) -> str:
        """
        Executes a list of queries using a `uopy.Command`
        object and returns the response from the last query.

        Parameters
        ----------
        queries : list[str]
            A list of UniData queries to be executed.
        clear_selects : bool, optional
            Optionally run the `CLEARSELECT ALL` command
            before querying. Defaults to True.
        stop_on_error : bool, optional
            Whether to raise on first TCL/ECL real error. Defaults to True.

        Returns
        -------
        str
            The response from the last query.
        """

        results = ""
        cmd = self.cmd
        # cmd = uopy.Command(session=self.session)

        # Reset UniData select lists
        if clear_selects:
            self.logger.debug("Resetting UniData select lists.")
            cmd.command_text = "CLEARSELECT ALL"
            cmd.run()

        for query in queries:
            self.logger.debug(f"Query: {query}")

            try:
                cmd.command_text = query
                cmd.run()

                response = (cmd.response or "").strip()
                response_lower = response.lower()

                match = re.search(r"(\d+)\s+record", response_lower)
                record_count: Optional[int] = int(match.group(1)) if match else None

                is_error = any(
                    [
                        "syntax error" in response_lower,
                        "error" in response_lower,
                        "illegal attribute" in response_lower,
                        "unable to open" in response_lower,
                        "not found" in response_lower
                        and "records" not in response_lower,
                    ]
                )
                is_no_data = "no data" in response_lower

                cleaned_lines = self.__clean_response_lines(response)

                if is_error:
                    self.logger.error(
                        f"{query} ---------------> (Error): {cleaned_lines[0] if cleaned_lines else response}"
                    )

                    if stop_on_error:
                        raise RuntimeError(response)

                elif is_no_data:
                    self.logger.warning(f"{query} ---------------> (No data returned.)")

                else:
                    summary = (
                        f"{record_count} records" if record_count is not None else "OK"
                    )
                    self.logger.info(f"{query} ---------------> ({summary})")

                    for line in cleaned_lines:
                        self.logger.debug(f"[{query}]: {line}")

                results = response

            except Exception:
                self.logger.exception(f"Failed query: {query}")
                raise

        return results

    def get_data(
        self, filename: str, field_list: list[str], id_list: list[str] | None = None
    ) -> list:
        """
        Retrieves data from a file using the specified
        filename and field list.

        Parameters
        ----------
        filename : str
            The name of the file to retrieve data from.
        field_list : list[str]
            The list of fields to retrieve from the file.
        id_list : list[str], optional
            The list of IDs to retrieve from the file. Defaults
            to None (all records).

        Returns
        -------
        list
            The retrieved data from the file.
        """
        data: list = []
        try:
            data_file = uopy.File(name=filename, session=self.session)
            if id_list is None:
                select_list = uopy.List()
                id_list = select_list.read_list()  # type: ignore
            else:
                select_list = uopy.List()
                select_list.form_list(id_list)
                id_list = select_list.read_list()  # type: ignore
            data = data_file.read_named_fields(field_list=field_list, id_list=id_list)[
                3
            ]  # type: ignore
        except TypeError as e:
            error = str(sys.exc_info()[1])
            if "NoneType" in error:
                self.logger.warning(
                    f"No data was selected from file '{filename}' or list."
                )
            else:
                raise Exception(error)
        except Exception as e:
            self.logger.error(e)
            raise
        finally:
            self.logger.info(f"{len(data)} records returned from file '{filename}'.")
        return data

    def get_id_list(self, queries: list[str], filename: str) -> uopy.DynArray:
        """
        Retrieves the list of IDs from a file using a
        list of queries and a specified file.

        Parameters
        ----------
        queries : list[str]
            A list of UniData queries to be executed.
        filename : str
            The name of the file to retrieve the list from.

        Returns
        -------
        uopy.DynArray
            The list of IDs from the file.
        """
        self.make_requests(queries)
        data_file = uopy.File(name=filename, session=self.session)
        select_list = uopy.List()
        id_list = select_list.read_list()
        return id_list

    def close_connection(self) -> None:
        """
        Closes the connection to the database.
        This method disconnects the current session
        from the database using the `uopy.disconnect` function.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        self.session.close()

    def __clean_response_lines(self, response: str) -> list[str]:
        """
        Clean up messy UniData responses.
        Filters out unnecessary lines (hopefully all).
        """
        lines = [line.strip() for line in response.split("\n") if line.strip()]
        cleaned = []
        for line in lines:
            lower = line.lower()
            if "overwriting existing" in lower:
                continue
            if "the following record ids do not exist" in lower:
                cleaned.append("Some record IDs were missing. Ignored.")
                continue
            cleaned.append(line)

        return cleaned
