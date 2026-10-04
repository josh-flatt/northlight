import json
import logging
import pandas as pd
import sys
import re
import uopy

from importlib.resources import files
from dotenv import load_dotenv
from typing import Optional

from northlight.integrations.exceptions import ErrorLimitExceededError


class UniDataClient:
    def __init__(
        self,
        hostname: str,
        username: str,
        password: str,
        path: str,
        port: int,
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
        self._hostname = hostname
        self._username = username
        self._password = password
        self._path = path
        self._port = port
        self._logger = logging.getLogger(__name__)

        # Error codes can be viewed at:
        # https://docs.rocketsoftware.com/bundle/grv1653317862214_grv1653317862214/page/nhb1653316841876.html
        self.uopy_errors: dict = json.loads(
            files("northlight")
            .joinpath("resources/uopy_errorcodes.json")
            .read_text(encoding="utf-8")
        )

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
            host=self._hostname,
            user=self._username,
            password=self._password,
            account=self._path,
            port=self._port,
            encoding="iso-8859-1",
        )
        self.cmd = uopy.Command(session=self.session)
        return self.session

    def make_requests(
        self,
        queries: list[str],
        clear_selects: bool = True,
        stop_on_error: bool = True,
        stop_on_empty: bool = True,
    ) -> Optional[str]:
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
        stop_on_empty : bool, optional
            Whether to raise on empty result sets. Defaults to True.

        Returns
        -------
        Optional[str]
            The response from the last query, or None if
            `stop_on_empty` is True and an empty response is encountered.
        """

        results = ""
        cmd = self.cmd

        # Reset UniData select lists
        if clear_selects:
            self._logger.debug("Resetting UniData select lists.")
            cmd.command_text = "CLEARSELECT ALL"
            cmd.run()

        for query in queries:
            self._logger.debug(f"Query: {query}")

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
                    self._logger.error(
                        f"{query} ---------------> (Error): {cleaned_lines[0] if cleaned_lines else response}"
                    )

                    if stop_on_error:
                        raise RuntimeError(response)

                elif is_no_data:
                    self._logger.warning(
                        f"{query} ---------------> (No data returned.)"
                    )
                    if stop_on_empty:
                        return None

                else:
                    summary = (
                        f"{record_count} records" if record_count is not None else "OK"
                    )
                    self._logger.info(f"{query} ---------------> ({summary})")

                    for line in cleaned_lines:
                        self._logger.debug(f"[{query}]: {line}")

                results = response

            except Exception:
                self._logger.exception(f"Failed query: {query}")
                raise

        return results

    def get_file_data(
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
                self._logger.warning(
                    f"No data was selected from file '{filename}' or list."
                )
            else:
                raise Exception(error)
        except Exception as e:
            self._logger.error(e)
            raise
        finally:
            self._logger.info(f"{len(data)} records returned from file '{filename}'.")
        return data

    def update_file_data(
        self,
        file: str,
        id_list: list,
        field_list: list,
        data: list,
        max_errors: int = 25,
        is_test: bool = True,
    ) -> bool:
        """
        Applies updates to the specified file in the database.

        All updates are attempted within a single transaction. Individual update
        failures are logged and counted. If the total number of errors exceeds
        ``max_errors``, the transaction is rolled back. Otherwise, the transaction
        is committed unless ``is_test`` is True, in which case it is rolled back.

        Parameters
        ----------
        file : str
            The name of the file to update.
        id_list : list
            The list of record IDs to update.
        field_list : list
            The list of fields to update.
        data : list
            The list of new values to assign. If field_list contains multiple
            fields, the data should be structured accordingly as a list of lists.
        max_errors : int, optional
            The maximum number of errors allowed before rolling back the
            transaction. Defaults to 25.
        is_test : bool, optional
            A flag to indicate if this is a test run. Test runs always roll back
            the transaction. Defaults to True.

        Returns
        -------
        bool
            True if the transaction completed successfully without exceeding
            ``max_errors``.

        Raises
        ------
        ErrorLimitExceededError
            If the number of update errors exceeds ``max_errors``.
        RuntimeError
            If the database transaction cannot be started.
        """
        try:
            uopy_file = uopy.File(name=file, session=self.session)

            self.session.tx_start()

            if not self.session.tx_is_active():
                raise RuntimeError("Transaction is not active.")

            old_data: list[str] = uopy_file.read_named_fields(
                id_list=id_list, field_list=field_list
            )[
                3
            ]  # type: ignore

            responses: tuple = uopy_file.write_named_fields(
                id_list=id_list, field_list=field_list, field_data_list=data
            )

            response_codes: uopy.DynArray = responses[0]
            status_codes: uopy.DynArray = responses[1]
            ids: uopy.DynArray = responses[2]
            new_data: uopy.DynArray = responses[3]

            error_count = 0

            for i in range(len(response_codes)):

                record_id = ids[i]
                response_code = response_codes[i]

                status_msg = self.uopy_errors.get(
                    response_code,
                    {"Description": "Unknown error"},
                )["Description"]

                old_value = old_data[i] if old_data[i] != "" else "None"
                new_value = new_data[i] if new_data[i] != "" else "None"

                log_msg = (
                    f"{record_id} ({response_code} {status_msg}): "
                    f"{old_value} -> {new_value}"
                )

                if response_code != "0":
                    error_count += 1
                    self._logger.error(log_msg)
                else:
                    self._logger.info(log_msg)

            if error_count > max_errors:
                raise ErrorLimitExceededError(
                    f"Count of errors ({error_count}) exceeded maximum allowed ({max_errors}). Transaction rolled back."
                )

            if is_test:
                self.session.tx_rollback()
                self._logger.warning(
                    f"(Test) Succeeded with {error_count} error(s). Transaction rolled back."
                )
                return True

            self._logger.info(f"Transaction complete with {error_count} error(s).")

            self.session.tx_commit()
            self._logger.info("Transaction committed successfully.")

            return True

        except ErrorLimitExceededError as e:
            self._logger.critical(e)
            self.session.tx_rollback()
            raise

        except Exception as e:
            self._logger.critical(f"Unexpected exception occurred: {e}")
            self.session.tx_rollback()
            raise

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

    def call_subroutine(self, sub_name: str, args: list[str]) -> list[str]:
        """
        Calls a UniData subroutine with the specified arguments.

        Parameters
        ----------
        sub_name : str
            The name of the subroutine to call.
        args : list[str]
            The list of arguments to pass to the subroutine.
            Note: this list must be ordered according to the
            subroutine's expected argument order. INCLUDE the
            empty strings for unused arguments & the return
            argument, if applicable.

        Returns
        -------
        list[str]
            The list of arguments after the subroutine call.
        """

        num_args = len(args)
        subroutine: uopy.Subroutine = uopy.Subroutine(
            name=sub_name, num_args=num_args, session=self.session
        )

        for i in range(num_args):
            subroutine.args[i] = args[i]

        subroutine.call()

        return subroutine.args

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
