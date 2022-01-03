"""Fourget exceptions."""


class FourgetException(Exception):
    """Base exception."""

    def __init__(self, msg: str) -> None:
        super().__init__(msg)
        self.msg = msg


class MalformedThreadURLException(FourgetException):
    """Indicates thread URL doesn't look right."""

    def __init__(self, url: str) -> None:
        super().__init__(
            f"{url} does not look like a valid 4chan thread URL. Valid URLs take the "
            'form "https://boards.4channel.org/<board>/thread/<post_id>". The '
            '"4chan.org" domain may also be used.'
        )


class ThreadNotFoundException(FourgetException):
    """Indicates thread 404s from API."""

    def __init__(self, url: str) -> None:
        super().__init__(f"{url} cannot be found.")
