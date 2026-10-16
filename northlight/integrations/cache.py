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

        self._cache_dir = path
        self._cache_file = os.path.join(self._cache_dir, "cache.json")
        self._logger = logging.getLogger(__name__)
        if not os.path.exists(self._cache_file):
            os.makedirs(self._cache_dir, exist_ok=True)
            self._save_cache({})
        self._load_cache()
        removed = self._clear_expired()
        if removed > 0:
            self._logger.info(f"Cleared {removed} expired cache entries.")

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
        cache = {}
        cache = self._load_cache()
        entry = cache.get(key, None)

        data = None

        if key not in cache:
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
                return None
        self._logger.info(f"Key '{key}' found in cache.")
        data = self._load_pickle_file(entry["file"])
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
        cache = {}
        cache = self._load_cache()

        expires_dt = datetime.datetime.max
        expiration_timestamp = expires_dt.timestamp()
        if ttl is not None and ttl.total_seconds() < 0:
            raise ValueError("Expiration time cannot be in the past.")
        if ttl is not None:
            expiration_timestamp = (datetime.datetime.now() + ttl).timestamp()
            expires_dt = datetime.datetime.fromtimestamp(expiration_timestamp)
        cache[key] = {
            "file": f"{self._cache_dir}/{key}.pkl",
            "expires": expiration_timestamp,
            "saved_at": datetime.datetime.now().timestamp(),
        }
        tmp_file = cache[key]["file"]
        self._save_pickle_file(tmp_file, value)

        self._logger.info(
            f"Key '{key}' saved in cache with TTL {expires_dt.strftime('%m-%d-%Y %H:%M:%S')}."
        )
        self._save_cache(cache)

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
        cache = {}
        cache = self._load_cache()

        if key in cache:
            tmp_file = cache[key]["file"]
            del cache[key]
            self._save_cache(cache)
            self._delete_pickle_file(tmp_file)
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
        # Clear cache file
        cache = {}
        self._save_cache(cache)

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
        cache = {}
        cache = self._load_cache()

        now = datetime.datetime.now().timestamp()
        keys_to_delete = [
            key
            for key, entry in cache.items()
            if entry["expires"] is not None and entry["expires"] < now
        ]
        for key in keys_to_delete:
            expiration_dt = datetime.datetime.fromtimestamp(cache[key]["expires"])
            self._logger.info(
                f"Key '{key}' has expired (was {expiration_dt.strftime('%m-%d-%Y %H:%M:%S')})."
            )

            # Remove .pkl file if exists
            tmp_file = cache[key]["file"]
            self._delete_pickle_file(tmp_file)

            del cache[key]
            self._logger.info(f"Key '{key}' removed.")

        self._save_cache(cache)
        return len(keys_to_delete)

    def _load_cache(self) -> dict:
        """
        Loads cache from file.

        Returns
        -------
        dict
            The loaded cache as a dictionary.
        """
        cache = {}
        if os.path.exists(self._cache_file):
            try:
                with open(self._cache_file, "r") as f:
                    cache = json.load(f)
            except json.JSONDecodeError:
                cache = {}
                self._logger.warning(
                    "Cache file is empty or corrupted. Starting with an empty cache."
                )
            except Exception as e:
                cache = {}
                self._logger.warning(
                    f"Unexpected error while loading cache file: {e}. Starting with an empty cache."
                )
        else:
            cache = {}
            self._logger.info(
                f"Cache file '{self._cache_file}' not found. Initializing empty cache."
            )
        return cache

    def _save_cache(self, cache: dict) -> None:
        """
        Saves the current state of the cache to the file specified by self._cache_file.

        Returns
        -------
        None
        """

        cache_info = {}

        if not cache:
            self._logger.warning("Saving empty cache.")
            with open(self._cache_file, "w") as f:
                json.dump({}, f, indent=4)
            return

        for key in cache:
            cache_info[key] = {
                "expires": cache[key]["expires"],
                "saved_at": cache[key]["saved_at"],
                "file": cache[key]["file"],
            }
            self._logger.debug(f"Cache info for '{key}': {cache_info[key]}")

        self._logger.info(f"Saving cache metadata to {self._cache_file}.")
        if not cache_info:
            self._logger.warning("No cache info found. Saving empty cache.")
            with open(self._cache_file, "w") as f:
                json.dump({}, f, indent=4)
            return

        with open(self._cache_file, "w") as f:
            json.dump(cache_info, f, indent=4)
        self._logger.info("Cache saved.")
        return

    def _load_pickle_file(self, file_path: str) -> Any:
        """
        Loads a pickle file from the given file path.

        Parameters
        ----------
        file_path : str
            The path to the pickle file to load.

        Returns
        -------
        Any
            The object loaded from the pickle file.
        """

        data = None
        try:
            with open(file_path, "rb") as f:
                data = pickle.load(f)
        except FileNotFoundError:
            self._logger.warning(f"Pickle file '{file_path}' not found.")
            return None
        except EOFError:
            self._logger.warning(f"Pickle file '{file_path}' is empty or incomplete.")
            self._delete_pickle_file(file_path)
            return None
        except Exception as e:
            self._logger.warning(
                f"Unexpected error while loading pickle file '{file_path}': {e}"
            )
            self._delete_pickle_file(file_path)
            return None
        return data

    def _save_pickle_file(self, file_path: str, obj: Any) -> None:
        """
        Saves an object to a pickle file at the given file path.

        Parameters
        ----------
        file_path : str
            The path to the pickle file to save.
        obj : Any
            The object to save to the pickle file.

        Returns
        -------
        None
        """
        try:
            with open(file_path, "wb") as f:
                pickle.dump(obj, f)
        except Exception as e:
            self._logger.warning(f"Failed to save pickle file '{file_path}': {e}")

    def _delete_pickle_file(self, file_path: str) -> None:
        """
        Deletes the pickle file at the given file path.

        Parameters
        ----------
        file_path : str
            The path to the pickle file to delete.

        Returns
        -------
        None
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            self._logger.error(f"Failed to delete pickle file '{file_path}': {e}")
            raise e
