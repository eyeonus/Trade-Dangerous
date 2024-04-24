from pathlib import Path

from .. import fs
from ..commands.exceptions import CommandLineError
from . import PluginException, ImportPluginBase

class ImportPlugin(ImportPluginBase):
    """
    Plugin that imports multiple .price files at once
    """
    
    PRICE_GLOB = "*.prices"
    BATCH_FILE = "batch.prices"
    
    pluginOptions = {
        'files': 'Path to some .price files to import (file=file1;file2)',
        'folder': 'Path to a folder containing .price files (folder=pathToFolder)'
    }
    
    def __init__(self, tdb, tdenv):
        super().__init__(tdb, tdenv)
    
    """
    Returns the newest file.
    """
    def file_get_newer(self, a, b):
        if a.stat().st_mtime > b.stat().st_mtime:
            return a
        else:
            return b
    
    """
    Returns a list of stations in a file
    """
    def file_get_stations(self, a):
        contents = a.read_text()
        stations = []
        for line in contents.split("\n"):
            if "@" in line:
                stations.append(line[2:])
        return stations
    
    """
    Given a list of files, does analysis to determine
    whether they are duplicates.
    """
    def sanitize_files(self, files):
        stations_seen = {}
        
        for f in files:
            filePath = Path(f)
            if not filePath.is_file():
                raise CommandLineError("File not found: {}".format(
                    str(filePath)
                ))
            
            stations = self.file_get_stations(filePath)
            
            # Does not support resolving multiple stations (yet)
            if len(stations) > 1:
                raise PluginException("EDMC Batch unable to process files with multiple stations. Use normal import.")
            
            for s in stations:
                if s in stations_seen:
                    cur_file = stations_seen[s]
                    # Set the newer file as the one we'll use.
                    stations_seen[s] = self.file_get_newer(cur_file, f)
                else:
                    stations_seen[s] = f
        
        return stations_seen.values()
    
    """
    Set the environment for the import command to import our files
    """
    def set_environment(self, files):
        tdenv = self.tdenv
        path_list = files
        fs.ensurefolder(tdenv.tmpDir)
        batchfile = tdenv.tmpDir / Path(self.BATCH_FILE)
        if batchfile.exists():
            batchfile.unlink()
        # We now have a list of paths. Add all contents to a new file
        temp_file = open(batchfile, "w")
        
        for f in path_list:
            contents = f.read_text()
            temp_file.writelines("# File: {}\n".format(f))
            temp_file.write(contents)
        
        # Set the file we're reading from to the temp file
        tdenv.filename = str(batchfile.absolute())
    
    def split_files(self, files):
        file_list = self.getOption("files").split(";")
        path_list = []
        for f in file_list:
            path_list.append(Path(f))
        return path_list
    
    def get_prices_in_folder(self, directory):
        folderToSplit = Path(directory)
        if not folderToSplit.is_dir():
            raise CommandLineError("Path is not a directory: {}".format(
                str(folderToSplit)
            ))
        
        filesInFolder = folderToSplit.glob(self.PRICE_GLOB)
        file_list = []
        for i in filesInFolder:
            file_list.append(i)
        
        return file_list
    
    def run(self):
        # Grab files option and validate
        files = self.getOption("files")
        folder = self.getOption("folder")
        
        if files is None and folder is None:
            raise PluginException("Argument Required")
        
        # The list of files to import...
        file_list = []
        
        if files:
            file_list.extend(self.split_files(files))
        if folder:
            file_list.extend(self.get_prices_in_folder(folder))
        
        # Split into a path list, verify all paths are good.
        self.set_environment(self.sanitize_files(file_list))
        return True

