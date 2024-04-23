"""
DirectOutput.py - Saitek DirectOutput.dll Python Wrapper

Version: 0.3
Author: Oliver "kfsone" Smith <oliver@kfs.org> 2014
Original Author: Frazzle

Description: Python wrapper class for DirectOutput functions.

This module consists of two classes - DirectOutput and DirectOutputDevice

DirectOutput directly calls C functions within DirectOutput.dll to allow Python control of the Saitek X52 Pro MFD and LEDs. Implemented as a class to allow sharing of dll object amongst functions

DirectOutputDevice is a wrapper around DirectOutput which automates setup and persists the device handle across functions. This class can be directly called or inherited to control an individual device (eg. X52 Pro)

Thanks to Spksh and ellF for the C# version of the wrapper which was very helpful in implementing this.
Thanks to Frazzle for the first Python version (no-longer compatible with the saitek driver).

Example Usage:

device = DirectOutputDevice()
device.AddPage(0, "Test", True)
device.SetString(0, 0, "Test String")

import time, sys
while True:
    try:
        time.sleep(1)
    except:
        #This is used to catch Ctrl+C, calling finish method is *very* important to de-initalize device.
        device.finish()
        sys.exit()

Saitek appear to periodically change the DLLs functions. At time of writing,
these are the functions listed in the DLL:

DirectOutput_Initialize
DirectOutput_Deinitialize
DirectOutput_AddPage
DirectOutput_DeleteFile
DirectOutput_DisplayFile
DirectOutput_Enumerate
DirectOutput_GetDeviceInstance
DirectOutput_GetDeviceType
DirectOutput_RegisterDeviceCallback
DirectOutput_RegisterPageCallback
DirectOutput_RegisterSoftButtonCallback
DirectOutput_RemovePage
DirectOutput_SaveFile
DirectOutput_SendServerFile
DirectOutput_SendServerMsg
DirectOutput_SetImage
DirectOutput_SetImageFromFile
DirectOutput_SetLed
DirectOutput_SetProfile
DirectOutput_SetString

DirectOutput_StartServer
DirectOutput_CloseServer

"""

from tradedangerous.mfd import MissingDeviceError

import ctypes
import ctypes.wintypes
import logging
import os
import platform
import sys
import time

S_OK = 0x00000000
E_HANDLE = 0x80070006
E_INVALIDARG = 0x80070057
E_OUTOFMEMORY = 0x8007000E
E_PAGENOTACTIVE = -0xfbffff        # Something munges it from it's actual value
E_BUFFERTOOSMALL = -0xfc0000
E_NOTIMPL = 0x80004001
ERROR_DEV_NOT_EXIST = 55

SOFTBUTTON_SELECT = 0x00000001
SOFTBUTTON_UP = 0x00000002
SOFTBUTTON_DOWN = 0x00000004


class DirectOutput:
    def __init__(self, dll_path):
        """
        Creates python object to interact with DirecOutput.dll
        
        Required Arguments:
        dll_path -- String containing DirectOutput.dll location.
        
        """
        logging.debug("DirectOutput.__init__")
        self.DirectOutputDLL = ctypes.WinDLL(dll_path)
    
    def Initialize(self, application_name):
        """
        Function to call DirectOutput_Initialize
        
        Required Arguments:
        application_name -- String representing name of applicaiton - must be unique per-application
        
        Returns:
        S_OK: The call completed sucesfully
        E_OUTOFMEMORY: There was insufficient memory to complete this call.
        E_INVALIDARG: The argument is invalid
        E_HANDLE: The DirectOutputManager process could not be found
        
        """
        logging.debug("DirectOutput.Initialize")
        return self.DirectOutputDLL.DirectOutput_Initialize(ctypes.wintypes.LPWSTR(application_name))
    
    def Deinitialize(self):
        """
        Direct function call to DirectOutput_Deinitialize
        
        Returns:
        S_OK: The call completed successfully.
        E_HANDLE:  DirectOutput was not initialized or was already deinitialized.
        """
        logging.debug("DirectOutput.Deinitialize")
        return self.DirectOutputDLL.DirectOutput_Deinitialize()
    
    def RegisterDeviceCallback(self, function):
        """
        Registers self.DeviceCallback to be called when devices get registered
        
        Required Arugments:
        function -- Function to call when a device registers
        
        Returns:
        S_OK: The call completed successfully
        E_HANDLE: DirectOutput was not initialized.
        
        """
        logging.debug("DirectOutput.RegisterDeviceCallback")
        return self.DirectOutputDLL.DirectOutput_RegisterDeviceCallback(function, 0)
    
    def Enumerate(self, function):
        """
        Direct call to DirectOutput_Enumerate
        
        Returns:
        S_OK: The call completed successfully
        E_HANDLE: DirectOutput was not initialized.
        
        """
        logging.debug("DirectOutput.Enumerate")
        return self.DirectOutputDLL.DirectOutput_Enumerate(function, 0)


    def RegisterSoftButtonCallback(self, device_handle, function):
        """
        Registers a function to be called when a soft button changes
        
        Required Arugments:
        device_handle -- ID of device
        function -- Function to call when a soft button changes
        
        Returns:
        S_OK: The call completed successfully.
        E_HANDLE: The device handle specified is invalid.
        """
        
        logging.debug("DirectOutput.RegisterSoftButtonCallback({}, {})".format(device_handle, function))
        return self.DirectOutputDLL.DirectOutput_RegisterSoftButtonCallback(ctypes.wintypes.HANDLE(device_handle), function, 0)
    
    def RegisterPageCallback(self, device_handle, function):
        """
        Registers a function to be called when page changes
        
        Required Arugments:
        device_handle -- ID of device
        function -- Function to call when a page changes
        
        Returns:
        S_OK: The call completed successfully.
        E_HANDLE: The device handle specified is invalid.
        """
        logging.debug("DirectOutput.RegisterPageCallback({}, {})".format(device_handle,function))
        return self.DirectOutputDLL.DirectOutput_RegisterPageCallback(ctypes.wintypes.HANDLE(device_handle), function, 0)
    
    def SetProfile(self, device_handle, profile):
        """
        Sets the profile used on the device.
        
        Required Arguments:
        device_handle -- ID of device
        profile -- full path of the profile to activate. passing None will clear the profile.
        """
        logging.debug("DirectOutput.SetProfile({}, {})".format(device_handle, profile))
        if profile:
            return self.DirectOutputDLL.DirectOutput_SetProfile(ctypes.wintypes.HANDLE(device_handle), len(profile), ctypes.wintypes.LPWSTR(profile))
        else:
            return self.DirectOutputDLL.DirectOutput_SetProfile(ctypes.wintypes.HANDLE(device_handle), 0, 0)
    
    def AddPage(self, device_handle, page, name, active):
        """
        Adds a page to the MFD
        
        Required Arguments:
        device_handle -- ID of device
        page -- page ID to add
        name -- String specifying page name
        active -- True if page is to become the active page, if False this will not change the active page
        
        Returns:
        S_OK: The call completed successfully.
        E_OUTOFMEMORY: Insufficient memory to complete the request.
        E_INVALIDARG: The dwPage parameter already exists.
        E_HANDLE: The device handle specified is invalid.
        
        """
        logging.debug("DirectOutput.AddPage({}, {}, {}, {})".format(device_handle, page, name, active))
        return self.DirectOutputDLL.DirectOutput_AddPage(ctypes.wintypes.HANDLE(device_handle), page, active)
    
    def RemovePage(self, device_handle, page):
        """
        Removes a page from the MFD
        
        Required Arguments:
        device_handle -- ID of device
        page -- page ID to remove
        
        Returns:
        S_OK: The call completed successfully.
        E_INVALIDARG: The dwPage argument does not reference a valid page id.
        E_HANDLE: The device handle specified is invalid.
        
        """
        logging.debug("DirectOutput.RemovePage({}, {})".format(device_handle, page))
        return self.DirectOutputDLL.DirectOutput_RemovePage(ctypes.wintypes.HANDLE(device_handle), page)
    
    def SetLed(self, device_handle, page, led, value):
        """
        Sets LED state on a given page
        
        Required Arguments:
        device_handle -- ID of device
        page -- page number
        led -- ID of LED to change
        value -- value to set LED (1 = on, 0 = off)
        
        Returns:
        S_OK: The call completes successfully.
        E_INVALIDARG: The dwPage argument does not reference a valid page id, or the dwLed argument does not specifiy a valid LED id.
        E_HANDLE: The device handle specified is invalid
        
        """
        logging.debug("DirectOutput.SetLed({}, {}, {}, {})".format(device_handle, page, led, value))
        return self.DirectOutputDLL.DirectOutput_SetLed(ctypes.wintypes.HANDLE(device_handle), page, led, value)


    def SetString(self, device_handle, page, line, string):
        """
        Sets a string to display on the MFD
        
        Required Arguments:
        device_handle -- ID of device
        page -- the ID of the page to add the string to
        line -- the line to display the string on (0 = top, 1 = middle, 2 = bottom)
        string -- the string to display
        
        Returns:
        S_OK: The call completes successfully.
        E_INVALIDARG: The dwPage argument does not reference a valid page id, or the dwString argument does not reference a valid string id.
        E_OUTOFMEMORY: Insufficient memory to complete the request.
        E_HANDLE: The device handle specified is invalid.
        
        """
        logging.debug("DirectOutput.SetString({}, {}, {}, {})".format(device_handle, page, line, string))
        return self.DirectOutputDLL.DirectOutput_SetString(ctypes.wintypes.HANDLE(device_handle), page, line, len(string), ctypes.wintypes.LPWSTR(string))


class DirectOutputDevice:
    
    class Buttons:
        
        select, up, down = False, False, False
        
        def __init__(self, bitmask):
            self.bitmask = bitmask
            if bitmask == 1:
                self.select = True
            elif bitmask == 2:
                self.up = True
            elif bitmask == 3:
                self.up = True
                self.select = True
            elif bitmask == 4:
                self.down = True
            elif bitmask == 5:
                self.down = True
                self.select = True
            elif bitmask == 6:
                self.up = True
                self.down = True
            elif bitmask == 7:
                self.up = True
                self.down = True
                self.select = True
        
        def __repr__(self):
            return "Select: "+str(self.select)+" Up: "+str(self.up)+" Down: "+str(self.down)
    
    application_name = "GenericDevice"
    device_handle = None
    direct_output = None
    debug_level = 0
    
    def __init__(self, debug_level=0, name=None):
        """
        Initialises device, creates internal state (device_handle) and registers callbacks.
        
        """
        
        logging.info("DirectOutputDevice.__init__")
        
        prog_dir = os.environ["ProgramFiles"]
        if platform.machine().endswith('86'):
            # 32-bit machine, nothing to worry about
            pass
        elif platform.machine().endswith('64'):
            # 64-bit machine, are we a 32-bit python?
            if platform.architecture()[0] == '32bit':
                prog_dir = os.environ["ProgramFiles(x86)"]
        dll_path = os.path.join(prog_dir, "Logitech\\DirectOutput\\DirectOutput.dll")
        
        self.application_name = name or DirectOutputDevice.application_name
        self.debug_level = debug_level
        
        try:
            logging.debug("DirectOutputDevice -> DirectOutput: {}".format(dll_path))
            self.direct_output = DirectOutput(dll_path)
            logging.debug("direct_output = {}".format(self.direct_output))
        except WindowsError as e:
            logging.warning("DLLError: {}: {}".format(dll_path, e.winerror))
            raise DLLError(e.winerror) from None
        
        result = self.direct_output.Initialize(self.application_name)
        if result != S_OK:
            logging.warning("direct_output.Initialize returned {}".format(result))
            raise DirectOutputError(result)
        
        logging.info("Creating callback closures.")
        self.onDevice_closure = self._OnDeviceClosure()
        logging.debug("onDevice_closure is {}".format(self.onDevice_closure))
        self.onEnumerate_closure = self._OnEnumerateClosure()
        logging.debug("onEnumerate_closure is {}".format(self.onEnumerate_closure))
        self.onPage_closure = self._OnPageClosure()
        logging.debug("onPage_closure is {}".format(self.onPage_closure))
        self.onSoftButton_closure = self._OnSoftButtonClosure()
        logging.debug("onSoftButton_closure is {}".format(self.onSoftButton_closure))
        
        result = self.direct_output.RegisterDeviceCallback(self.onDevice_closure)
        if result != S_OK:
            logging.warning("RegisterDeviceCallback failed: {}".format(result))
            self.finish()
            raise DirectOutputError(result)
        
        result = self.direct_output.Enumerate(self.onEnumerate_closure)
        if result != S_OK:
            logging.warning("Enumerate failed: {}".format(result))
            self.finish()
            raise DirectOutputError(result)
        
        if not self.device_handle:
            logging.warning("No device handle")
            self.finish()
            raise MissingDeviceError()
        
        result = self.direct_output.RegisterSoftButtonCallback(self.device_handle, self.onSoftButton_closure)
        if result != S_OK:
            logging.warning("RegisterSoftButtonCallback failed")
            self.finish()
            raise DirectOutputError(result)
        
        result = self.direct_output.RegisterPageCallback(self.device_handle, self.onPage_closure)
        if result != S_OK:
            logging.warning("RegisterPageCallback failed")
            self.finish()
            raise DirectOutputError(result)


    def __del__(self, *args, **kwargs):
        logging.debug("DirectOutputDevice.__del__")
        self.finish()


    def finish(self):
        """
        De-initializes DLL. Must be called before program exit
        
        """
        if self.direct_output:
            logging.info("DirectOutputDevice deinitializing")
            self.direct_output.Deinitialize()
            self.direct_output = None
        else:
            logging.debug("nothing to do in finish()")


    def _OnDeviceClosure(self):
        """
        Returns a pointer to function that calls self._OnDevice method. This allows class methods to be called from within DirectOutput.dll
        
        http://stackoverflow.com/questions/7259794/how-can-i-get-methods-to-work-as-callbacks-with-python-ctypes
        
        """
        OnDevice_Proto = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.c_bool, ctypes.c_void_p)
        
        def func(hDevice, bAdded, pvContext):
            logging.info("device callback closure func: {}, {}, {}".format(hDevice, bAdded, pvContext))
            self._OnDevice(hDevice, bAdded, pvContext)
        
        return OnDevice_Proto(func)


    def _OnEnumerateClosure(self):
        """
        Returns a pointer to function that calls self._OnEnumerate method. This allows class methods to be called from within DirectOutput.dll
        
        http://stackoverflow.com/questions/7259794/how-can-i-get-methods-to-work-as-callbacks-with-python-ctypes
        
        """
        OnEnumerate_Proto = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)
        
        def func(hDevice, pvContext):
            logging.info("enumerate callback closure func: {}, {}".format(hDevice, pvContext))
            self._OnEnumerate(hDevice, pvContext)
        
        return OnEnumerate_Proto(func)


    def _OnPageClosure(self):
        """
        Returns a pointer to function that calls self._OnPage method. This allows class methods to be called from within DirectOutput.dll
        
        http://stackoverflow.com/questions/7259794/how-can-i-get-methods-to-work-as-callbacks-with-python-ctypes
        
        """
        OnPage_Proto = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.wintypes.DWORD, ctypes.c_bool, ctypes.c_void_p)
        
        def func(hDevice, dwPage, bActivated, pvContext):
            logging.info("page callback closure: {}, {}, {}, {}".format(hDevice, dwPage, bActivated, pvContext))
            self._OnPage(hDevice, dwPage, bActivated, pvContext)
        
        return OnPage_Proto(func)


    def _OnSoftButtonClosure(self):
        """
        Returns a pointer to function that calls self._OnSoftButton method. This allows class methods to be called from within DirectOutput.dll
        
        http://stackoverflow.com/questions/7259794/how-can-i-get-methods-to-work-as-callbacks-with-python-ctypes
        
        """
        OnSoftButton_Proto = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.wintypes.DWORD, ctypes.c_void_p)
        
        def func(hDevice, dwButtons, pvContext):
            logging.info("soft button callback closure: {}, {}, {}".format(hDevice, dwButtons, pvContext))
            self._OnSoftButton(hDevice, dwButtons, pvContext)
        
        return OnSoftButton_Proto(func)


    def _OnDevice(self, hDevice, bAdded, pvContext):
        """
        Internal function to register device handle
        
        """
        if not bAdded:
            raise NotImplementedError("Received a message that a device went away.")
        if self.device_handle and self.device_handle != hDevice:
            raise IndexError("Too many Saitek devices present")
        logging.info("_OnDevice")
        self.device_handle = hDevice


    def _OnEnumerate(self, hDevice, pvContext):
        """
        Internal function to process a device enumeration
        
        """
        logging.info("_OnEnumerate")
        self._OnDevice(hDevice, True, pvContext)


    def _OnPage(self, hDevice, dwPage, bActivated, pvContext):
        """
        Method called when page changes. Calls self.OnPage to hide hDevice and pvContext from end-user
        
        """
        logging.info("_OnPage")
        self.OnPage(dwPage, bActivated)


    def _OnSoftButton(self, hDevice, dwButtons, pvContext):
        """
        Method called when soft button changes. Calls self.OnSoftButton to hide hDevice and pvContext from end-user. Also hides change of page softbutton and press-up.
        
        """
        logging.info("_OnSoftButton")
        self.OnSoftButton(self.Buttons(dwButtons))


    def OnPage(self, page, activated):
        """
        Method called when a page changes. This should be overwritten by inheriting class
        
        Required Arguments:
        page -- page_id passed to AddPage
        activated -- true if this page has become the active page, false if this page was the active page
        
        """
        logging.info("OnPage({}, {})".format(page, activated))


    def OnSoftButton(self, buttons):
        """
        Method called when a soft button changes. This should be overwritten by inheriting class
        
        Required Arguments:
        buttons - Buttons object representing button state
        
        """
        logging.info("OnSoftButton({})".format(buttons))


    def SetProfile(self, profile):
        """
        Sets the profile used on the device.
        
        Required Arguments:
        device_handle -- ID of device
        profile -- full path of the profile to activate. passing None will clear the profile.
        """
        logging.debug("SetProfile({})".format(profile))
        return self.direct_output.SetProfile(self.device_handle, profile)


    def AddPage(self, page, name, active):
        """
        Adds a page to the MFD. If overriden by a derived class, you should
        call super().AddPage(*args, **kwargs)
        
        Required Arguments:
        page -- page ID to add
        name -- String specifying page name
        active -- True if page is to become the active page, if False this will not change the active page
        
        """
        logging.info("AddPage({}, {}, {})".format(page, name, active))
        self.direct_output.AddPage(self.device_handle, page, name, active)


    def RemovePage(self, page):
        """
        Removes a page from the MFD
        
        Required Arguments:
        page -- page ID to remove
        
        """
        logging.info("RemovePage({})".format(page))
        result = self.direct_output.RemovePage(self.device_handle, page)
        if result != S_OK:
            logging.error("RemovePage failed: {}".format(result))
            self.finish()
            raise DirectOutputError(result)


    def SetString(self, page, line, string):
        """
        Sets a string to display on the MFD
        
        Required Arguments:
        page -- the ID of the page to add the string to
        line -- the line to display the string on (0 = top, 1 = middle, 2 = bottom)
        string -- the string to display
        """
        logging.debug("SetString({}, {}, {})".format(page, line, string))
        result = self.direct_output.SetString(self.device_handle, page, line, string)
        if result != S_OK:
            logging.warning("SetString failed: {}".format(result))
            self.finish()
            raise DirectOutputError(result)


    def SetLed(self, page, led, value):
        """
        Sets LED state on a given page
        
        Required Arguments:
        page -- page number
        led -- ID of LED to change
        value -- value to set LED (1 = on, 0 = off)
        
        """
        logging.debug("SetLed({}, {}, {})".format(page, led, value))
        result = self.direct_output.SetLed(self.device_handle, page, led, value)
        if result != S_OK:
            logging.warning("SetLed failed: {}".format(result))
            self.finish()
            raise DirectOutputError(result)


class DeviceNotFoundError(Exception):
    
    def __str__(self):
        return "No Compatible Device Found"


class DLLError(Exception):
    
    def __init__(self, error_code):
        self.error_code = error_code
        if error_code == 126:
            self.msg = "specified file does not exist"
        elif error_code == 193:
            self.msg = "possible 32/64 bit mismatch between Python interpreter and DLL. Make sure you have installed both the 32- and 64-bit driver from Saitek's website"
        else:
            self.msg = "unspecified error"
    
    def __str__(self):
        return "Unable to load DirectOutput.dll - "+self.msg


class DirectOutputError(Exception):
    Errors = {
        E_HANDLE : "Invalid device handle specified.",
        E_INVALIDARG : "An argument is invalid, and I don't mean it has a poorly leg.",
        E_OUTOFMEMORY : "Download more RAM.",
        E_PAGENOTACTIVE : "Page not active, stupid page.",
        E_BUFFERTOOSMALL : "Buffer used was too small. Use a bigger buffer. See also E_OUTOFMEMORY.",
        E_NOTIMPL : "Feature not implemented, allegedly"
    }
    
    def __init__(self, error_code):
        self.error_code = error_code
        if error_code in self.Errors:
            self.msg = self.Errors[error_code]
        else:
            self.msg = "Unspecified DirectOutput Error - "+str(hex(error_code))
    
    def __str__(self):
        return self.msg


if __name__ == '__main__':
    # If you want it to go to a file?
    # logging.basicConfig(filename='directoutput.log', filemode='w', level=logging.DEBUG, format='%(asctime)s %(name)s [%(filename)s:%(lineno)d] %(message)s')
    # If you want less verbose logging?
    # logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s [%(filename)s:%(lineno)d] %(message)s')
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)s [%(filename)s:%(lineno)d] %(message)s')
    
    device = DirectOutputDevice(debug_level=1)
    print("Device initialized")
    
    device.AddPage(0, "Test", True)
    print("Test Page added")
    
    device.SetString(0, 0, "Test String")
    print("Test String added")
    
    device.AddPage(1, "Other", False)
    device.AddPage(2, "Another", False)
    
    while True:
        try:
            time.sleep(1)
        except:  # noqa: E722
            # This is used to catch Ctrl+C, calling finish method is *very* important to de-initalize device.
            device.finish()
            sys.exit()
