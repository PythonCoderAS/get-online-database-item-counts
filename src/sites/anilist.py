from aiosqlite import Connection
from dataclasses import dataclass
from ..provider import Provider, ProviderRunArgs
from ..ratelimited_session import RatelimitedSession

async def setup_anilist_db(db: Connection):
    await db.execute("CREATE TABLE IF NOT EXISTS anilist(category varchar(15) PRIMARY KEY, last_page INT NOT NULL)")

@dataclass
class Page:
    items_on_page: int
    has_next_page: bool

def make_provider(pageAttribute: str, category: str, increment_pages_by: int = 500) -> Provider:

    query = """
    query($page:Int) {
        Page(page: $page, perPage:50){
            %s{
                id
            }
            pageInfo{
                hasNextPage
            }
        }
    }
    """ % pageAttribute

    async def get_data_for_page(page: int, session: RatelimitedSession) -> Page:
        async with session.post("https://graphql.anilist.co", json={"query": query, "variables": {"page": page}}) as resp:
            data = await resp.json()
        return Page(len(data["data"]["Page"][pageAttribute.split("(")[0]]), data["data"]["Page"]["pageInfo"]["hasNextPage"])

    async def run(run_args: ProviderRunArgs) -> int:
        db = run_args.db
        session = run_args.session
        assert db is not None
        cursor = await db.execute(f"SELECT last_page FROM anilist WHERE category = '{category}'")
        last_page_potential = await cursor.fetchone()
        if last_page_potential:
            last_page = int(last_page_potential[0])
        else:
            last_page = None
        await cursor.close()
        if last_page is None:
            start = 1
            end = None
            curpage = 1
            found_last_page = False
            while end is None:
                page_data = await get_data_for_page(curpage, session=session)
                if page_data.has_next_page:
                    curpage += increment_pages_by
                else:
                    start = curpage - increment_pages_by
                    end = curpage
            while (end - start) > 5:
                curpage = (start + end) // 2
                page_data = await get_data_for_page(curpage, session=session)
                if page_data.has_next_page:
                    start = curpage
                else:
                    end = curpage
                    if page_data.items_on_page > 0:
                        found_last_page = True
                        start = end = curpage
                        break
            last_page = start
        found_last_page = False
        count_on_last_page = 0
        while not found_last_page:
            page_data = await get_data_for_page(last_page, session=session)
            if not page_data.has_next_page:
                found_last_page = True
                count_on_last_page = page_data.items_on_page
                break
            last_page += 1
        await db.execute(f"INSERT OR REPLACE INTO anilist VALUES ('{category}', ?)", (last_page,))
        await db.commit()
        return 50 * (last_page - 1) + count_on_last_page

    return Provider(
        command_line_flag_name=f"anilist-{category}",
        run=run,
        needs_db=True,
        db_setup=setup_anilist_db,
        add_ratelimits={"https://graphql.anilist.co": 1},
    )

anime = make_provider("media(type:ANIME)", "anime")
manga = make_provider("media(type:MANGA)", "manga")
characters = make_provider("characters", "characters")
staff = make_provider("staff", "staff")
