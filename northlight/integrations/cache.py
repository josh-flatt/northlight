import datetime
import json
import logging
import os
import pickle

from typing import Any


class Cache:
    def __init__(self, path: str):
        """
        Initializes a new instance of the Cache class.

        On creation, creates an empty dictionary to
        store the cache entries in memory. Files added
        are saved as .pkl files, while metadata for each
        entry is kept in the cache.json file.

        The name of the cache file at the specified path
        is "cache.json".

        Parameters
        ----------
        path : str
            The path to the directory where the
            cache will be stored.

        Returns
        -------
        None
        """
        if path is None:
            path = "./cache"

        self._cache = {}
        self._cache_dir = path
        self._cache_file = os.path.join(self._cache_dir, "cache.json")
        self._logger = logging.getLogger(__name__)
        if not os.path.exists(self._cache_dir):
            os.makedirs(self._cache_dir)
        self._load_cache()
        removed = self._clear_expired()
        if removed > 0:
            self._logger.info(f"Cleared {removed} expired cache entries.")
            self._save_cache()

    def get(
        self, key: str, reference_time: datetime.datetime = datetime.datetime.now()
    ):
        """
        Retrieves a value from the cache by its key.

        Parameters
        ----------
        key : str
            The key of the cache entry to retrieve.
        reference_time : datetime.datetime, optional
            The time to check expiration against.
            Defaults to now.

        Returns
        -------
        any or None
            The value associated with the key, or
            None if the key has expired or does not exist.

        Raises
        ------
        None
        """

        entry = None
        with open(self._cache_file, "r") as f:
            try:
                self._cache = json.load(f)
            except json.JSONDecodeError:
                self._logger.warning(
                    "Cache file is empty or corrupted. Starting with an empty cache."
                )
                self._cache = {}
            entry = self._cache.get(key)

        # entry = self._cache.get(key)
        data = None

        if key not in self._cache:
            self._logger.info(f"Key '{key}' not found in cache.")
            return None
        if entry is None:
            self._logger.info(f"Key '{key}' not found in cache or entry is None.")

            return None
        if entry["expires"] is not None:
            if reference_time.timestamp() > entry["expires"]:
                expiration_dt = datetime.datetime.fromtimestamp(entry["expires"])
                self._logger.info(
                    f"Cache entry for key '{key}' has expired (was {expiration_dt.strftime('%m-%d-%Y %H:%M:%S')})."
                )
                self.delete(key)
                self._save_cache()
                return None
        self._logger.info(f"Key '{key}' found and valid in cache.")
        try:
            with open(entry["file"], "rb") as f:
                data = pickle.load(f)
        except FileNotFoundError:
            self._logger.warning(f"Cache file for key '{key}' not found.")
            self.delete(key)
            self._save_cache()
            return None
        except EOFError:
            self._logger.warning(
                f"Cache file for key '{key}' is empty or incomplete. Deleting."
            )
            self.delete(key)
            self._save_cache()
            return None
        return data

    def set(self, key: str, value: Any, ttl: datetime.timedelta | None = None):
        """
        Sets a value in the cache with an optional expiration time.

        Parameters
        ----------
        key : str
            The key under which the value will be stored.
        value : any
            The value to be stored in the cache.
        ttl : datetime.timedelta, optional
            The expiration time as a datetime.timedelta object
            representing the duration from now after which the
            cache entry should expire.
            If None, the value will not expire.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If the expiration time is in the past.
        """

        with open(self._cache_file, "r") as f:
            try:
                self._cache = json.load(f)
            except json.JSONDecodeError:
                self._cache = {}
                self._logger.warning(
                    "Cache file is empty or corrupted. Starting with an empty cache."
                )

        expires_dt = datetime.datetime.max
        expiration_timestamp = expires_dt.timestamp()
        if ttl is not None and ttl.total_seconds() < 0:
            raise ValueError("Expiration time cannot be in the past.")
        if ttl is not None:
            expiration_timestamp = (datetime.datetime.now() + ttl).timestamp()
            expires_dt = datetime.datetime.fromtimestamp(expiration_timestamp)
        self._cache[key] = {
            "file": f"{self._cache_dir}/{key}.pkl",
            "expires": expiration_timestamp,
            "saved_at": datetime.datetime.now().timestamp(),
        }
        with open(self._cache[key]["file"], "wb") as f:
            pickle.dump(value, f)

        self._logger.info(
            f"Key '{key}' saved in cache with TTL {expires_dt.strftime('%m-%d-%Y %H:%M:%S')}."
        )
        self._save_cache()

    def delete(self, key: str) -> bool:
        """
        Deletes a value from the cache by its key.

        Parameters
        ----------
        key : str
            The key of the cache entry to delete.

        Returns
        -------
        bool
            Success of deleting the cache entry.

        Raises
        ------
        None
        """

        with open(self._cache_file, "r") as f:
            try:
                self._cache = json.load(f)
            except json.JSONDecodeError:
                self._cache = {}
                self._logger.warning(
                    "Cache file is empty or corrupted. Starting with an empty cache."
                )

        if key in self._cache:
            tmp_file = self._cache[key]["file"]
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
            del self._cache[key]
            self._save_cache()
            return True
        self._logger.info(f"Key '{key}' not found in cache.")
        return False

    def clear(self) -> bool:
        """
        Clears all entries from the cache.

        Returns
        -------
        bool
            True if the cache was cleared successfully.

        Raises
        ------
        None
        """
        # Clear cache in memory
        self._cache = {}
        self._save_cache()

        # Clear .pkl files
        for file in os.listdir(self._cache_dir):
            if file.endswith(".pkl"):
                os.remove(os.path.join(self._cache_dir, file))

        return True

    def _clear_expired(self) -> int:
        """
        Clears all expired entries from the cache.

        Returns
        -------
        int
            The number of expired cache entries that were cleared.
        """

        with open(self._cache_file, "r") as f:
            try:
                self._cache = json.load(f)
            except json.JSONDecodeError:
                self._cache = {}
                self._logger.warning(
                    "Cache file is empty or corrupted. Starting with an empty cache."
                )

        now = datetime.datetime.now().timestamp()
        keys_to_delete = [
            key
            for key, entry in self._cache.items()
            if entry["expires"] is not None and entry["expires"] < now
        ]
        for key in keys_to_delete:
            expiration_dt = datetime.datetime.fromtimestamp(self._cache[key]["expires"])
            self._logger.info(
                f"Key '{key}' has expired (was {expiration_dt.strftime('%m-%d-%Y %H:%M:%S')})."
            )

            # Remove .pkl file if exists
            tmp_file = self._cache[key]["file"]
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
                self._logger.info(f"Removed tmp file {tmp_file}.")

            del self._cache[key]
            self._logger.info(f"Key '{key}' removed.")

        return len(keys_to_delete)

    def _load_cache(self):
        """
        Loads cache from file.

        Returns
        -------
        None
        """
        if os.path.exists(self._cache_file):
            with open(self._cache_file, "r") as f:
                self._cache = json.load(f)
        else:
            self._cache = {}
            self._logger.info(
                f"Cache file '{self._cache_file}' not found. Initializing empty cache."
            )

    def _save_cache(self):
        """
        Saves the current state of the cache to the file specified by self._cache_file.

        Returns
        -------
        None
        """

        cache_info = {}
        for key in self._cache:
            cache_info[key] = {
                "expires": self._cache[key]["expires"],
                "saved_at": self._cache[key]["saved_at"],
                "file": self._cache[key]["file"],
            }
            self._logger.debug(f"Cache info for '{key}': {cache_info[key]}")

        self._logger.info(f"Saving cache metadata to {self._cache_file}.")

        with open(self._cache_file, "w") as f:
            json.dump(cache_info, f, indent=4)
        self._logger.info("Cache saved.")
