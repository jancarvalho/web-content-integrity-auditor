from metadata import (
    __title__,
    __version__,
    __author__,
    __author_role__,
    __copyright__,
    __license__,
    __tagline__,
)


def print_banner() -> None:
    print(
        f"""
        {'=' * 72}

        WCIA - {__title__}

        Version: {__version__}

        {__tagline__}

        Designed and Developed by {__author__}
        {__author_role__}

        {__copyright__}
        License: {__license__}

        {'=' * 72}
        """
    )