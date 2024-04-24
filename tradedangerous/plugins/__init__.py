from textwrap import TextWrapper

import importlib

parent_name = '.'.join(__name__.split('.')[:-1])

class PluginException(Exception):
    """
    Base class for exceptions thrown by plugins.
    """


class PluginBase:
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
        """
        Parameters:
            tdb
                Instance of TradeDB
            tdenv
                Instance of TradeEnv
        """
        self.tdb = tdb
        self.tdenv = tdenv
        
        self.options = {}
        try:
            pluginOptions = self.pluginOptions
        except AttributeError:
            pluginOptions = {}
        
        for opt in tdenv.pluginOptions or []:
            equals = opt.find('=')
            if equals < 0:
                key, value = opt, True
            else:
                key, value = opt[:equals], opt[equals+1:]
            keyName = key.lower()
            if keyName not in pluginOptions:
                if keyName == "help":
                    raise SystemExit(self.usage())
                
                if not pluginOptions:
                    raise PluginException(
                        "This plugin does not support any options."
                    )
                
                raise PluginException(
                    "Unknown plugin option: '{}'.\n"
                    "\n"
                    "Valid options for this plugin:\n"
                    "  {}.\n"
                    "\n"
                    "Use '--opt=help' for details.\n"
                    .format(
                        opt,
                        ', '.join(
                            opt for opt in sorted(pluginOptions.keys())
                )))
            self.options[key.lower()] = value


    def usage(self):
        tw = TextWrapper(
                width=78,
                drop_whitespace=True,
                expand_tabs=True,
                fix_sentence_endings=True,
                break_long_words=True,
                break_on_hyphens=True,
        )
        
        text = tw.fill(self.__doc__.strip()) + "\n\n"
        
        try:
            options = self.pluginOptions
        except AttributeError:
            return text + "This plugin does not support any options.\n"
        
        tw.subsequent_indent=' ' * 24
        text += "Options supported by this plugin:\n"
        for opt in sorted(options.keys()):
            text += "--opt={:<12}  ".format(opt)
            text += tw.fill(options[opt].strip()) + "\n"
        text += "\n"
        text += "You can also chain options together, e.g.:\n"
        text += "  --opt={}\n".format(",".join(list(options.keys())[:3]))
        
        return text


    def getOption(self, key):
        """
        Case-sensitive plugin-option lookup.
        """
        lkey = key.lower()
        try:
            return self.options[lkey]
        except KeyError:
            return None


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
        raise Warning("Plugin did not implement finish()")
        return True


class ImportPluginBase(PluginBase):
    """
    Base class for import plugins.
    
    Called by "import" as soon as argument parsing has been done.
    
    An import plugin implements "run()" and "finish()".
    
    On entry to the "import" function, before the database has
    been loaded or the cache file generated, the plugin's
    "run()" member is invoked.
    
    This function can do as much or as little work as you need.
    
    When you are done, return True to allow "import" to continue,
    e.g. for example a plugin that simply sets the cmdenv.url to
    a specific download would return True.
    
    On the other hand, if you complete all the import work
    relevant to your plugin, return None or False and the command
    will early-out.
    
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
        """
        Parameters:
            tdb
                Instance of TradeDB
            tdenv
                Instance of TradeEnv
        """
        super().__init__(tdb, tdenv)


    def run(self):
        """
        Plugin Must Implement:
        
        Called immediately on entry to the import_cmd.run() function.
        This means that you have no database access via the tdb object.
        
        If you need to access data from the .db file, you should put
        that code in the "finish()" object.
        
        Returns:
            True if you want the "import" command to continue (e.g.
            to reach the call to "finish()",
            False or None to early out after your return.
        """
        raise PluginException("Not implemented")


    def finish(self):
        """
        Plugin Must Implement:
        
        Called after import has rebuilt the cache, loaded the DB data
        into it's TradeDB instance, done any downloads and checked for
        the presence of cmdenv.filename, but before it has tried to
        import the .prices data.
        
        Returns:
            True if you want the "import" command to continue and
            try to import the .prices data,
            False or None to early out after your return.
        """
        self.tdenv.WARN("Plugin did not implement finish()")
        return True


def load(pluginName, typeName):
    """
    Attempt to load a plugin and find the specified plugin
    class within it.
    """
    
    # Check if a file matching this name exists.
    moduleName = __name__+".{}_plug".format(pluginName.lower())
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

