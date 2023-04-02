from dataclasses import dataclass
from ...provider import Provider, ProviderRunArgs
from ...ratelimited_session import RatelimitedSession

query = """
query($page:Int) {
  Page(page: $page, perPage:50){
    media(type:ANIME){
      id
    }
    pageInfo{
      hasNextPage
    }
  }
}
"""

@dataclass
class AnimePage:
    items_on_page: int
    has_next_page: bool

async def get_data_for_page(page: int, session: RatelimitedSession) -> AnimePage:
    async with session.post("https://graphql.anilist.co", json={"query": query, "variables": {"page": page}}) as resp:
        data = await resp.json()
    return AnimePage(len(data["data"]["Page"]["media"]), data["data"]["Page"]["pageInfo"]["hasNextPage"])

async def run(run_args: ProviderRunArgs) -> int:
    db = run_args.db
    session = run_args.session
    assert db is not None
    cursor = await db.execute("SELECT last_page FROM anilist WHERE category = 'anime'")
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
                curpage += 250
            else:
                start = curpage - 250
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
    await db.execute("INSERT OR REPLACE INTO anilist VALUES ('anime', ?)", (last_page,))
    await db.commit()
    return 50 * (last_page - 1) + count_on_last_page

anilist_anime = Provider(
    command_line_flag_name="anilist-anime",
    run=run,
    needs_db=True,
)