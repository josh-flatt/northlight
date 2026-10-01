import json
import os
import datetime
import logging


class Cache:
    def __init__(self, path: str):
        """
        Initializes a new instance of the Cache class.

        On creation, creates an empty dictionary to
        store the cache entries. It also keeps track
        through the use of a json file for long-term storage.

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
        self._cache = {}
        self._path = path
        self._cache_file = os.path.join(self._path, "cache.json")
        self._logger = logging.getLogger(__name__)
        if not os.path.exists(self._path):
            os.makedirs(self._path)
        self._load_cache()
        removed = self._clear_expired()
        if removed > 0:
            self._logger.info(f"Cleared {removed} expired cache entries.")
            self._save_cache()

    def get(self, key):
        """
        Retrieves a value from the cache by its key.

        Parameters
        ----------
        key : str
            The key of the cache entry to retrieve.

        Returns
        -------
        any or None
            The value associated with the key, or
            None if the key has expired or does not exist.

        Raises
        ------
        None
        """

        entry = self._cache.get(key)

        if key not in self._cache:
            self._logger.info(f"Key '{key}' not found in cache.")
            return None
        if entry is None:
            self._logger.info(f"Cache entry for key '{key}' is None.")
            return None
        if entry["expires"] is not None:
            if datetime.datetime.now().timestamp() > entry["expires"]:
                self._logger.info(
                    f"Cache entry for key '{key}' has expired (was {entry['expires']})."
                )
                del self._cache[key]
                self._save_cache()
                return None
        return entry["value"]

    def set(self, key, value, expires: datetime.timedelta | None = None):
        """
        Sets a value in the cache with an optional expiration time.

        Parameters
        ----------
        key : str
            The key under which the value will be stored.
        value : any
            The value to be stored in the cache.
        expires : datetime.timedelta, optional
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
        if expires is not None and expires.total_seconds() < 0:
            raise ValueError("Expiration time cannot be in the past.")
        if expires is not None:
            expiration_timestamp = (datetime.datetime.now() + expires).timestamp()
        else:
            expiration_timestamp = None
        self._cache[key] = {
            "value": value,
            "expires": expiration_timestamp,
        }
        self._save_cache()

    def delete(self, key) -> bool:
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
        if key in self._cache:
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
        self._cache = {}
        self._save_cache()
        return True

    def _clear_expired(self) -> int:
        """
        Clears all expired entries from the cache.

        Returns
        -------
        int
            The number of expired cache entries that were cleared.
        """
        now = datetime.datetime.now().timestamp()
        keys_to_delete = [
            key
            for key, entry in self._cache.items()
            if entry["expires"] is not None and entry["expires"] < now
        ]
        for key in keys_to_delete:
            del self._cache[key]
        if keys_to_delete:
            self._save_cache()
        return len(keys_to_delete)

    def _load_cache(self):
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
        with open(self._cache_file, "w") as f:
            json.dump(self._cache, f)
