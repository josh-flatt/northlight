from pathlib import Path
from datetime import datetime
import shutil


def move(src: str | Path, dest: str | Path):
    """
    Moves a file or directory to a new location.

    Parameters
    ----------
    src : str, Path
        Source path.
    dest : str, Path
        Destination path.

    Returns
    -------
    None
    """
    src = Path(src)
    dest = Path(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(src, dest)


def copy(src: str | Path, dest: str | Path):
    """
    Copies a file or directory to a new location.

    Parameters
    ----------
    src : str, Path
        Source path.
    dest : str, Path
        Destination path.

    Returns
    -------
    None
    """
    src = Path(src)
    dest = Path(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)

    if src.is_dir():
        shutil.copytree(src, dest, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dest)


def delete(path: str | Path):
    """
    Deletes a file or directory. Again, this will
    delete a directory.

    Consider using `clear_directory` if you want
    to keep the directory, but delete its contents.

    Parameters
    ----------
    path : str, Path
        Path to delete.

    Returns
    -------
    None

    See Also
    --------
    clear_directory : Deletes all contents of a
        directory, leaving the directory itself.
    """
    path = Path(path)

    if not path.exists():
        return

    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def clear_directory(directory: str | Path):
    """
    Deletes all contents of a directory, leaving the directory itself.

    Parameters
    ----------
    directory : str, Path
        Path of directory to clear.

    Returns
    -------
    None
    """
    path = Path(directory)

    if not path.exists():
        return

    for item in path.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def backup(src: str | Path, backup_dir: str | Path):
    """
    Backups a file or a directory's contents to a new location.

    Parameters
    ----------
    src : str, Path:
        Path to source file or directory.
    backup_dir : str, Path:
        Destination path.

    Returns
    -------
    None
    """
    date = datetime.now()
    fancy_date = date.strftime("%Y-%m-%d")

    src = Path(src)
    backup_dir = Path(backup_dir)

    backup_dir.mkdir(parents=True, exist_ok=True)

    if src.is_dir():

        for item in src.iterdir():

            destination = backup_dir / f"{item.stem}_{fancy_date}{item.suffix}"

            copy(item, destination)
    else:

        destination = backup_dir / f"{src.stem}_{fancy_date}{src.suffix}"
        copy(src, destination)
