from dataclasses import dataclass
from typing import Coroutine, Callable, Any
from aiosqlite import Connection
from argparse import Namespace, _ArgumentGroup
from .ratelimited_session import RatelimitedSession

@dataclass
class ProviderRunArgs:
    args: Namespace
    db: Connection | None
    session: RatelimitedSession

@dataclass(kw_only=True)
class Provider:
    """The flag name to invoke this collector."""
    command_line_flag_name: str
    run: Callable[[ProviderRunArgs], Coroutine[Any, Any, int]]
    post_add_arg_parser_config: Callable[[_ArgumentGroup], None] | None = None
    """Used to generate the argument group name. Only used when ``post_add_arg_parser_config`` is not None. Defailts to the flag name."""
    argument_group_name: str | None = None
    argument_group_description: str | None = None
    include_in_all_flag: bool = True
    db_setup: Callable[[Connection], Coroutine[Any, Any, Any]] | None = None
    """If this is set to true, ensure the database exists before running this provider. Set to True if db_setup is not None."""
    needs_db: bool = False
    """If any ratelimits need to be added to the session, this will add them. Expects a dict with keys being the origin and values being the ratelimit in seconds."""
    add_ratelimits: dict[str, float] | None = None