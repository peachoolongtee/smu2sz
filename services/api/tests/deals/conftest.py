"""The deal and document reads run on the API's in-memory runtime: the same `client` fixture as tests/api."""

from tests.api.conftest import client  # noqa: F401
