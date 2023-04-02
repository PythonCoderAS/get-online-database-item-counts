from aiohttp import ClientSession
from asyncio import Lock, sleep
from time import monotonic

class RatelimitedSession(ClientSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ratelimits: dict[str, float] = {}
        self.ratelimit_locks: dict[str, Lock] = {}
        self.last_request_time: dict[str, float] = {}

    def add_ratelimit(self, origin: str, ratelimit: float):
        self.ratelimits[origin] = ratelimit
        self.ratelimit_locks[origin] = Lock()
        self.last_request_time[origin] = 0

    async def _request(self, method: str, str_or_url, **kwargs):
        url = self._build_url(str_or_url)
        lock = self.ratelimit_locks.get(url.origin, None)
        if lock:
            async with lock:
                time_to_sleep = self.last_request_time[url.origin] + self.ratelimits[url.origin] - monotonic()
                if time_to_sleep > 0:
                    await sleep(time_to_sleep)
                self.last_request_time[url.origin] = monotonic()
                return await super()._request(method, str_or_url, **kwargs)
        else:
            return await super()._request(method, str_or_url, **kwargs)