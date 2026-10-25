import httpx

from airlock.proc import CommandError

RELEASE_ERRORS = (OSError, ValueError, LookupError, CommandError, httpx.HTTPError)
