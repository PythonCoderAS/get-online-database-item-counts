from aiosqlite import Connection

async def setup_anilist_db(db: Connection):
    await db.execute("CREATE TABLE IF NOT EXISTS anilist(category varchar(15) PRIMARY KEY, last_page INT NOT NULL)")

from .anime import anilist_anime
from .manga import anilist_manga

for provider in [anilist_anime, anilist_manga]:
    provider.db_setup = setup_anilist_db
    provider.add_ratelimits = {"https://graphql.anilist.co": 1}

del provider