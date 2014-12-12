import importlib


class PluginException(Exception):
    """
    Base class for exceptions thrown by plugins.
    """


class PluginBase(object):
    """
    Base class for plugin implementation.

    To implement a plugin, create a file in the plugins directory
    called "mypluginname_plug.py". This file should implement
    plugin classes derived from the appropriate plugins base,
    e.g. for an import pluggin:

        import plugins

        class ImportPlugin(plugins.ImportPluginBase):
            # your implementation here
    """

    def __init__(self, tdb, tdenv):
        self.tdb = tdb
        self.tdenv = tdenv


    def run(self):
        """
        Plugin must implement: Execute the plugin's logic.

        Called by the parent module before it does any validation
        of arguments and before it does any processing work.

        Return True to allow the calling module to continue working,
        e.g. if your plugin simply changes the tdenv.

        Return False if you have completed work and the calling
        module can finish.
        """
        raise Exception("Plugin did not implement run()")


    def finish(self):
        """
        Plugin may need to implement: Called after all preparation
        work has been done by the sub-command invoking the plugin.

        Return False if you have completed all neccessary work.
        Returning True will allow the sub-command to finish its
        normal workflow after you return.
        """
        raise Exception("Plugin did not implement finish()")


class ImportPluginBase(PluginBase):
    """
    Base class for import plugins.

    Called by "import" as soon as argument parsing has been done.

    An import plugin implements "run()" and "finish()". The
    run sub-command invokes "run()" before it does any argument
    parsing or validation.

    If your plugin does all the work neccessary to achieve your
    import, it should return False to indicate "job done". The
    import command will then exit immediately.

    If you return True, the import command will proceed with
    argument checking, downloading data if a URL was provided
    by the user or configured by your module.

    "finish()" will then be called before the import command
    tries to import the data. This gives you an opportunity to
    modify, parse or even import the data yourself.

    Returning False from finish() ends processing, the import
    command will rebuild the main .prices file and exit. This
    allows you to write a plugin that does its own processing
    of a custom .prices format, for example.

    Returning True will allow the import command to proceed
    with import as normal. This allows, for example, a plugin
    that pre-processes the .prices file before import is called.
    """

    defaultImportFile = "import.prices"

    def __init__(self, tdb, tdenv):
        super().__init__(tdb, tdenv)
        self.tdb = tdb
        self.tdenv = tdenv


    def run(self):
        """
        Plugin Must Implement:
        Called immediately on import command startup; should return
        True if import needs to continue proceesing, or False if the
        plugin did everything that needs to be done.
        """
        raise PluginException("Not implemented")


    def finish(self):
        """
        Plugin Must Implement:
        Called prior to the last step of import, before the actual
        call to cache.importDataFromFile is invoked.
        Returning False will cause the import command to exit,
        returning True will allow the call to importDataFromFile
        to proceed as usual.
        """
        raise PluginException("Not implemented")


def load(pluginName, typeName):
    """
    Attempt to load a plugin and find the specified plugin
    class within it.
    """

    # Check if a file matching this name exists.
    moduleName = "plugins.{}_plug".format(pluginName.lower())
    try:
        importedModule = importlib.import_module(moduleName)
    except ImportError as e:
        raise PluginException("Unable to load plugin '{}': {}".format(
                pluginName, str(e),
        ))

    pluginClass = getattr(importedModule, typeName, None)
    if not pluginClass:
        raise PluginException("{} plugin does not provide a {}.".format(
                pluginName, typeName,
        ))

    return pluginClass
