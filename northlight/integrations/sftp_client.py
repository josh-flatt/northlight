import os
import logging
import paramiko
import warnings
from dotenv import load_dotenv
from io import StringIO


class SFTPClient:
    def __init__(
        self,
        host: str,
        port: str,
        username: str,
        password: str | None = None,
        ssh_key: str | None = None,
        ssh_key_path: str | None = None,
        ssh_key_type: str = "ed25519",
    ) -> None:
        """
        Initializes a new instance of the SFTPClient class.

        Parameters
        ----------
        host : str
            The hostname of the SFTP server.
        port : str
            The port of the SFTP server.
        username : str
            The username to use for authentication.
        password : str | None
            The password to use for authentication.
        ssh_key : str | None
            The SSH key to use for authentication.
        ssh_key_path : str | None
            The path to the SSH key to use for authentication.
        ssh_key_type : str
            The type of SSH key to use for authentication.
            Options are `ed25519` and `rsa`. Defaults to `ed25519`.
            Case insensitive.

        Calls
        -----
        `open_connection()`
            Opens the connection to the SFTP server.
        """
        self.sftp_host = host
        self.sftp_port = port
        self.sftp_user = username
        self.sftp_pass = password
        self.sftp_ssh_key = ssh_key
        self.sftp_ssh_key_path = ssh_key_path
        self.sftp_ssh_key_type = ssh_key_type

        self.logger = logging.getLogger(__name__)
        self.transport: paramiko.Transport = None  # type: ignore
        self.sftp: paramiko.SFTPClient = None  # type: ignore
        self.connection_open: bool = False

        self.open_connection()

        return

    def open_connection(self) -> None:
        """
        Opens the connection to the SFTP server.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Raises
        ------
        ValueError
            * If neither password nor ssh_key is provided for authentication.
        """

        self.logger.info(
            f"Connecting to source SFTP: {self.sftp_host}:{self.sftp_port}"
        )
        self.transport: paramiko.Transport = paramiko.Transport(
            (self.sftp_host, int(self.sftp_port))
        )
        self.transport.banner_timeout = 60
        if self.sftp_ssh_key:
            if self.sftp_ssh_key_type.lower() == "ed25519":
                private_key = paramiko.Ed25519Key.from_private_key(
                    StringIO(self.sftp_ssh_key)
                )
            elif self.sftp_ssh_key_type.lower() == "rsa":
                private_key = paramiko.RSAKey.from_private_key(
                    StringIO(self.sftp_ssh_key)
                )
            else:
                raise ValueError(f"Unsupported SSH key type: {self.sftp_ssh_key_type}")
            self.transport.connect(username=self.sftp_user, pkey=private_key)
        elif self.sftp_ssh_key_path:
            if self.sftp_ssh_key_type.lower() == "ed25519":
                private_key = paramiko.Ed25519Key.from_private_key_file(
                    self.sftp_ssh_key_path
                )
            elif self.sftp_ssh_key_type.lower() == "rsa":
                private_key = paramiko.RSAKey.from_private_key_file(
                    self.sftp_ssh_key_path
                )
            else:
                raise ValueError(f"Unsupported SSH key type: {self.sftp_ssh_key_type}")
            self.transport.connect(username=self.sftp_user, pkey=private_key)
        elif self.sftp_pass:
            self.transport.connect(username=self.sftp_user, password=self.sftp_pass)
        else:
            raise ValueError(
                "Either password or ssh_key must be provided for authentication."
            )
        self.sftp: paramiko.SFTPClient = paramiko.SFTPClient.from_transport(self.transport)  # type: ignore
        self.connection_open = True
        return

    def close_connection(self) -> None:
        """
        Closes the connection to the SFTP server.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        self.logger.info("Closing Connection To SFTP.")
        self.transport.close()
        self.sftp.close()
        self.connection_open = False
        return

    def upload_files(
        self,
        local_dir: str,
        remote_dir: str,
        files: str | list[str] | None = None,
        permissions: int | None = None,
        existing_ok: bool = True,
        empty_ok: bool = False,
    ) -> None:
        """
        Uploads a file or list of files to the SFTP server.

        Parameters
        ----------
        local_dir : str
            The directory on the local machine to upload from.
        remote_dir : str
            The directory on the SFTP server to upload to.
        files : str, list[str], optional
            The file(s) to upload. If None, all files
            in the local directory will be uploaded.
        permissions : int, optional
            File permissions to set on remote. Example: `0o760`.
            Defaults to None.
        existing_ok : bool, optional
            Whether it's ok if the file already exists
            on the remote server. Defaults to True.
        empty_ok : bool, optional
            Whether it's ok if the local file has a size of 0.
            Defaults to False.

        Returns
        -------
        None

        Raises
        ------
        FileNotFoundError
            * If the local file is not found or has a size of 0.
        FileExistsError
            * If the remote file already exists and existing_ok is False.
        Exception
            * If the local file size does not match the remote file size.
        """
        try:
            if self.connection_open == False:
                self.logger.warning("Connection To SFTP Not Open.")
                self.open_connection()

            local_files = os.listdir(local_dir)

            if files is None:
                if (
                    len(local_files) == 0
                ):  # os.listdir() returns an empty list if the directory is empty.
                    self.logger.error("Error: No files found in local directory")
                    raise FileNotFoundError("No files found in local directory")
                files = local_files

            if type(files) == str:
                files = [files]

            self.logger.info("Uploading File(s) To SFTP")

            remote_size = 0

            for file in files:
                local_path: str = f"{local_dir}/{file}"
                remote_path: str = f"{remote_dir}/{file}"
                self.logger.info(f"Local File Path: {local_path}")
                self.logger.info(f"Remote File Path: {remote_path}")

                if not os.path.isfile(local_path):
                    self.logger.error(f"Error: Local file not found at {local_path}")
                    raise FileNotFoundError(f"Local file not found at '{local_path}'")

                # Check Local File Size
                local_size = os.stat(local_path).st_size
                self.logger.info(f"Local File Size: {local_size}")
                if local_size == 0:
                    if not empty_ok:
                        raise FileNotFoundError(
                            f"Local File '{file}' exists but has no size in working directory"
                        )

                # Check If File Exists On Remote
                contents: list[str] = []
                remote_contents = self.sftp.listdir(remote_dir)
                if remote_contents is not None:
                    contents = remote_contents
                for existing_file in contents:
                    self.logger.info(f"Existing File: {existing_file}")
                if file in contents:
                    if not existing_ok:
                        self.logger.error(
                            f"Remote File '{file}' already exists on Remote"
                        )
                        # sftp.remove(remote_path)
                        raise FileExistsError(
                            f"Remote File '{file}' already exists on Remote"
                        )
                    else:
                        self.logger.info(
                            f"Remote File '{file}' already exists on Remote"
                        )
                else:
                    self.logger.info(f"Remote File '{file}' does not exist")

                # Upload File
                if (local_size and local_size > 0) or (local_size == 0 and empty_ok):
                    self.logger.info(f"Uploading {file} To SFTP")
                    self.sftp.put(localpath=local_path, remotepath=remote_path)
                else:
                    raise FileNotFoundError(
                        f"Local File '{file}' exists but has no size in working directory"
                    )

                # Check if file exists on Remote after upload
                remote_contents = self.sftp.listdir(remote_dir)
                if remote_contents is not None:
                    contents = remote_contents
                if file in contents:
                    file_stats = self.sftp.stat(remote_path)
                    if type(file_stats.st_size) == int:
                        remote_size = file_stats.st_size
                else:
                    raise FileNotFoundError(
                        f"Upload Failed - File '{file}' does not exist on Remote"
                    )

                self.logger.info(f"Local File Size: {local_size}")
                self.logger.info(f"Remote File Size: {remote_size}")
                if local_size == remote_size:
                    self.logger.info(f"File '{file}' uploaded successfully to Remote")
                else:
                    raise Exception(
                        f"File '{file}' size mismatch. Local: {local_size}, Remote: {remote_size}"
                    )

                if permissions is not None:
                    self.logger.info(
                        f"Attempting to change permissions on Remote file to {permissions}"
                    )
                    self.sftp.chmod(path=remote_path, mode=permissions)
                    # self.logger.info("Attempting to change permissions on Remote file to 760")
                    # sftp.chmod(path=remote_path, mode=0o760)

                self.logger.info(f"File '{file}' uploaded successfully to Remote")

            self.logger.info("File Upload Complete")
        except Exception as e:
            self.logger.exception(e)
            self.close_connection()
            raise

    def fetch_files(
        self,
        local_dir: str,
        remote_dir: str,
        files: str | list[str] | None = None,
        remove: bool = False,
        missing_ok: bool = True,
    ) -> list[str]:
        """
        Gets a list of files from the SFTP server, and
        downloads them to the working directory. It will
        also remove the files from the SFTP server if remove is True.

        Parameters
        ----------
        local_dir : str
            The local directory to download files to.
        remote_dir : str
            The directory on the SFTP server to fetch filesfrom.
        files : str, list[str], optional
            A list of file names to fetch. If None, all files
            will be fetched.
        remove : bool, optional
            Whether to remove the files from the SFTP server.
            Defaults to False.
        missing_ok : bool, optional
            Whether to ignore missing files on the SFTP server.
            Defaults to True.

        Returns
        -------
        list[str]
            A list of the downloaded file names.

        Raises
        ------
        FileNotFoundError
            * If a specified file is not found on the SFTP server.
        Exception
            * If the local file size does not match the remote file size.
        """
        try:
            specified_files: list[str] = []
            if self.connection_open == False:
                self.logger.warning("Connection To SFTP Not Open.")
                self.open_connection()
            if files is not None:
                if type(files) == str:
                    specified_files = [files]
                elif type(files) == list:
                    specified_files = files

            remote_contents = self.sftp.listdir(remote_dir)
            self.logger.info(f"Files found on source SFTP: {remote_contents}")

            if remote_contents is None:
                raise FileNotFoundError(
                    f"Remote Directory '{remote_dir}' does not exist on SFTP."
                )

            files_to_fetch: list[str] = []
            self.logger.info(
                f"Specified Files ({len(specified_files)}): {specified_files}"
            )

            if len(specified_files) == 0:
                files_to_fetch = remote_contents
            else:
                files_to_fetch = list(
                    set(remote_contents).intersection(set(specified_files))
                )
            self.logger.info(f"Files to fetch: {files_to_fetch}")
            for file in specified_files:
                if file not in remote_contents:
                    if missing_ok:
                        self.logger.info(f"File '{file}' not found on SFTP. Skipping.")
                        continue
                    else:
                        raise FileNotFoundError(f"File '{file}' not found on SFTP.")
            self.logger.info(f"Files to fetch: {files_to_fetch}")

            fetched: list[str] = []

            if not os.path.exists(local_dir):
                os.makedirs(local_dir)
                self.logger.info(f"Created Directory: {local_dir}")

            for file in files_to_fetch:
                local_path: str = f"{local_dir}/{file}"
                remote_path: str = f"{remote_dir}/{file}"
                self.logger.info(f"Local File Path: {local_path}")
                self.logger.info(f"Remote File Path: {remote_path}")

                self.logger.info(f"Downloading: {remote_path} -> {local_path}")
                self.sftp.get(remotepath=remote_path, localpath=local_path)

                local_size = os.stat(local_path).st_size
                remote_size = self.sftp.stat(remote_path).st_size

                self.logger.info(
                    f"Remote size: {remote_size} | Local size: {local_size}"
                )

                if local_size != remote_size:
                    raise Exception(
                        f"Size mismatch for '{file}'. "
                        f"Remote: {remote_size}, Local: {local_size}"
                    )

                self.logger.info(f"Downloaded successfully: {file}")
                if remove:
                    self.sftp.remove(remote_path)
                    self.logger.info(f"Removed from remote: {remote_path}")
                fetched.append(file)

            self.logger.info(f"Fetch complete. {len(fetched)} file(s) downloaded.")
        except Exception as e:
            self.logger.exception(e)
            self.close_connection()
            raise
        return fetched
