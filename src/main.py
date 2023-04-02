from pathlib import Path
from aiosqlite import connect, Connection
from importlib import import_module
from argparse import ArgumentParser, Namespace
from csv import writer
from json import dumps

from .provider import Provider, ProviderRunArgs
from .ratelimited_session import RatelimitedSession

class Main:
    def __init__(self):
        self.db: Connection | None = None
        self.output_file: Path | None = None
        self.session: RatelimitedSession = None
        self.arg_parser = ArgumentParser(description="A tool to collect item counts from various sources.")
        self.arg_parser.add_argument("--all", action="store_true", help="Collect data from all sources.")
        display_option_group = self.arg_parser.add_mutually_exclusive_group(required=True)
        display_option_group.add_argument("--print", action="store_true", help="Print the data to the console.")
        display_option_group.add_argument("--save-csv", action="store", help="Save the data to a CSV file.", metavar="FILE_PATH")
        display_option_group.add_argument("--save-json", action="store", help="Save the data to a JSON file.", metavar="FILE_PATH")
        display_option_group.add_argument("--save-db", action="store", help="Save the data to the SQLite database under the given table (will delete previous table contents if it exists).", metavar="TABLE_NAME")

    async def setup_db(self):
        self.db = await connect(Path(__file__).parent.parent / "database.db.sqlite")

    async def close_db(self):
        await self.db.close()

    def get_run_args(self, args: Namespace) -> ProviderRunArgs:
        return ProviderRunArgs(args=args, db=self.db, session=self.session)
    
    def get_potential_providers(self):
        sites = Path(__file__).parent / "sites"
        modules = list(sites.glob("*.py")) + list(item.parent for item in sites.glob("*/__init__.py"))
        modules.remove(sites / "__init__.py")
        providers: list[Provider] = []
        for module in modules:
            imported_module = import_module(f"src.sites.{module.stem}")
            providers.extend(attr for attr in vars(imported_module).values() if isinstance(attr, Provider))
        return providers
    
    async def main(self):
        try:
            providers = self.get_potential_providers()
            for provider in providers:
                if provider.post_add_arg_parser_config is not None:
                    group = self.arg_parser.add_argument_group(title=provider.argument_group_name or provider.command_line_flag_name, description=provider.argument_group_description)
                    group.add_argument(f"--{provider.command_line_flag_name}", action="store_true", help=f"Collect data from {provider.argument_group_name or provider.command_line_flag_name}.")
                    provider.post_add_arg_parser_config(group)
                else:
                    self.arg_parser.add_argument(f"--{provider.command_line_flag_name}", action="store_true", help=f"Collect data from {provider.argument_group_name or provider.command_line_flag_name}.")
            args = self.arg_parser.parse_args()
            to_run = [provider for provider in providers if getattr(args, provider.command_line_flag_name.replace("-", "_")) or (args.all and provider.include_in_all_flag)]
            for provider in to_run:
                if self.session is None:
                    self.session = RatelimitedSession()
                if provider.add_ratelimits is not None:
                    for origin, ratelimit in provider.add_ratelimits.items():
                        self.session.add_ratelimit(origin, ratelimit)
                if not self.db and (provider.db_setup is not None or provider.needs_db):
                    await self.setup_db()
                if provider.db_setup is not None:
                    await provider.db_setup(self.db)
                result = await provider.run(self.get_run_args(args))
                if args.print:
                    print(f"{provider.command_line_flag_name}: {result}")
                if args.save_csv:
                    if not self.output_file:
                        self.output_file = Path(args.save_csv).open("w")
                        csv_writer = writer(self.output_file)
                        csv_writer.writerow(["Provider", "Result"])
                    csv_writer = writer(self.output_file)
                    csv_writer.writerow([provider.command_line_flag_name, result])
                if args.save_json:
                    if not self.output_file:
                        self.output_file = Path(args.save_json).open("w")
                    self.output_file.write(dumps([provider.command_line_flag_name, result]))
                if args.save_db:
                    print(args.save_db)
                    if not self.db:
                        await self.setup_db()
                        cursor = await self.db.execute(f"CREATE TABLE IF NOT EXISTS {args.save_db} (provider TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY (provider))")
                        await cursor.execute(f"DELETE FROM {args.save_db}")
                    await self.db.execute_insert(f"INSERT INTO {args.save_db} VALUES (?, ?)", (provider.command_line_flag_name, str(result)))
        finally:
            if self.db:
                await self.close_db()
            if self.output_file:
                self.output_file.close()
            if self.session:
                await self.session.close()