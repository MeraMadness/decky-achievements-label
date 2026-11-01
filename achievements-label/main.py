class Plugin:
    # This plugin is frontend-only. The empty backend exists just so Decky
    # loads it the same way it loads plugins that have one.
    async def _main(self):
        pass

    async def _unload(self):
        pass
