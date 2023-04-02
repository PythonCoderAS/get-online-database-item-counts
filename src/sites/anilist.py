from ..provider import Provider, ProviderRunArgs


def make_provider(category: str) -> Provider:

    query = """

    query {
    SiteStatistics {
        %s(perPage: 25, sort: DATE_DESC) {
        nodes {
            date
            count
        }
        }
    }
    }


    """ % category

    async def run(run_args: ProviderRunArgs) -> int:
        session = run_args.session
        async with session.post("https://graphql.anilist.co", json={"query": query}) as resp:
            data = await resp.json()
        return data["data"]["SiteStatistics"][category]["nodes"][0]["count"]

    return Provider(
        command_line_flag_name=f"anilist-{category}",
        run=run,
        needs_db=False,
        add_ratelimits={"https://graphql.anilist.co": 1},
    )

anime = make_provider("anime")
manga = make_provider("manga")
characters = make_provider("characters")
staff = make_provider("staff")
