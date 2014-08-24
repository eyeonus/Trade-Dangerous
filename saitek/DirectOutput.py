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

import ctypes
import ctypes.wintypes

S_OK = 0x00000000
E_HANDLE = 0x80070006
E_INVALIDARG = 0x80070057
E_OUTOFMEMORY = 0x8007000E
E_PAGENOTACTIVE = -0xfbffff        # Something munges it from it's actual value
E_BUFFERTOOSMALL = -0xfc0000
E_NOTIMPL = 0x80004001

SOFTBUTTON_SELECT = 0x00000001
SOFTBUTTON_UP = 0x00000002
SOFTBUTTON_DOWN = 0x00000004

class TaggedSpan(object):
    indentLevel = ""
    def __init__(self, name, enabled):
        self.name = name
        self.enabled = enabled
        if self.enabled: print("%s-> %s" % (TaggedSpan.indentLevel, self.name))
        TaggedSpan.indentLevel += '--'
    def __del__(self, *args, **kwargs):
        TaggedSpan.indentLevel = TaggedSpan.indentLevel[:-2]
        if self.enabled: print("%s<- %s" % (TaggedSpan.indentLevel, self.name))

class DirectOutput(object):

    def __init__(self, dll_path):
        """
        Creates python object to interact with DirecOutput.dll

        Required Arguments:
        dll_path -- String containing DirectOutput.dll location.

        """
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
        return self.DirectOutputDLL.DirectOutput_Initialize(ctypes.wintypes.LPWSTR(application_name))

    def Deinitialize(self):
        """
        Direct function call to DirectOutput_Deinitialize

        Returns:
        S_OK: The call completed successfully.
        E_HANDLE:  DirectOutput was not initialized or was already deinitialized.
        """
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
        return self.DirectOutputDLL.DirectOutput_RegisterDeviceCallback(function, 0)

    def Enumerate(self, function):
        """
        Direct call to DirectOutput_Enumerate

        Returns:
        S_OK: The call completed successfully
        E_HANDLE: DirectOutput was not initialized.

        """
        return self.DirectOutputDLL.DirectOutput_Enumerate(function, 0)


    def RegisterSoftButtonCallback(self, device_handle, function):
        """
        Registers self.RegisterSoftButtonCallback to be called when a soft button changes

        Required Arugments:
        device_handle -- ID of device
        function -- Function to call when a soft button changes

        Returns:
        S_OK: The call completed successfully.
        E_HANDLE: The device handle specified is invalid.

        """
        return self.DirectOutputDLL.DirectOutput_RegisterSoftButtonCallback(device_handle, function, 0)

    def RegisterPageCallback(self, device_handle, function):
        """
        Registers self.RegisterPageCallback to be called when page changes

        Required Arugments:
        device_handle -- ID of device
        function -- Function to call when a page changes

        Returns:
        S_OK: The call completed successfully.
        E_HANDLE: The device handle specified is invalid.
        """
        return self.DirectOutputDLL.DirectOutput_RegisterPageCallback(device_handle, function, 0)

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
        return self.DirectOutputDLL.DirectOutput_AddPage(device_handle, page, active)


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
        return self.DirectOutputDLL.DirectOutput_RemovePage(device_handle, page)

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
        return self.DirectOutputDLL.DirectOutput_SetLed(device_handle, page, led, value)


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
        return self.DirectOutputDLL.DirectOutput_SetString(device_handle, page, line, len(string), ctypes.wintypes.LPWSTR(string))


class DirectOutputDevice(object):

    class Buttons(object):

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

    def __init__(self, dll_path="C:\\Program Files (x86)\\Saitek\\DirectOutput\\DirectOutput.dll", debug_level=0, name=None):

        """
        Initialises device, creates internal state (device_handle) and registers callbacks.

        """

        self.application_name = name or DirectOutputDevice.application_name

        self.debug_level = debug_level
        outerSpan = TaggedSpan("Initializing SaitekX52Pro", debug_level >= 1)

        try:
            innerSpan = TaggedSpan("Creating DirectOutput instance", debug_level >= 2)
            self.direct_output = DirectOutput(dll_path)
        except WindowsError as e:
            raise DLLError(e.winerror) from None

        innerSpan = TaggedSpan("Initializing DirectOutput(%s)" % self.application_name, debug_level >= 2)
        result = self.direct_output.Initialize(self.application_name)
        if result != S_OK:
            raise DirectOutputError(result)
        del innerSpan

        innerSpan = TaggedSpan("Creating callback closures", debug_level >= 2)
        self.device_callback_instance = self._DeviceCallbackClosure()
        self.enumerate_callback_instance = self._EnumerateCallbackClosure()
        self.register_page_callback_instance = self._RegisterPageCallbackClosure()
        self.register_soft_button_callback_instance = self._RegisterSoftButtonCallbackClosure()
        del innerSpan

        innerSpan = TaggedSpan("Registering device callback", debug_level >= 2)
        result = self.direct_output.RegisterDeviceCallback(self.device_callback_instance)
        if result != S_OK:
            self.finish()
            raise DirectOutputError(result)
        del innerSpan

        innerSpan = TaggedSpan("Enumerating devices", debug_level >= 2)
        result = self.direct_output.Enumerate(self.enumerate_callback_instance)
        if result != S_OK:
            self.finish()
            raise DirectOutputError(result)
        del innerSpan

        if not self.device_handle:
            self.finish()
            raise DirectOutputError(result)

        innerSpan = TaggedSpan("Registering page callback", debug_level >= 2)
        result = self.direct_output.RegisterPageCallback(self.device_handle, self.register_page_callback_instance)
        if result != S_OK:
            self.finish()
            raise DirectOutputError(result)
        del innerSpan

        innerSpan = TaggedSpan("Registering soft button callback", debug_level >= 2)
        result = self.direct_output.RegisterSoftButtonCallback(self.device_handle, self.register_soft_button_callback_instance)
        if result != S_OK:
            self.finish()
            raise DirectOutputError(result)
        del innerSpan

    def __del__(self, *args, **kwargs):
        span = TaggedSpan("~DirectOutputDevice", self.debug_level >= 2)
        self.finish()

    def debug(self, level, *args, **kwargs):
        if self.debug_level >= level:
            print(*args, **kwargs)

    def finish(self):
        """
        De-initializes DLL. Must be called before program exit

        """
        span = TaggedSpan("DirectOutputDevice.finish()", self.debug_level >= 2)
        if self.direct_output:
            self.direct_output.Deinitialize()
            self.direct_output = None

    def _DeviceCallbackClosure(self):
        """
        Returns a pointer to function that calls self._DeviceCallback method. This allows class methods to be called from within DirectOutput.dll

        http://stackoverflow.com/questions/7259794/how-can-i-get-methods-to-work-as-callbacks-with-python-ctypes

        """
        DeviceCallback_Proto = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.c_bool, ctypes.c_void_p)
        def func(hDevice, bAdded, pvContext):
            span = TaggedSpan("devicecallback closure", debug_level >= 2)
            self._DeviceCallback(hDevice, bAdded, pvContext)
        return DeviceCallback_Proto(func)

    def _EnumerateCallbackClosure(self):
        """
        Returns a pointer to function that calls self._EnumerateCallback method. This allows class methods to be called from within DirectOutput.dll

        http://stackoverflow.com/questions/7259794/how-can-i-get-methods-to-work-as-callbacks-with-python-ctypes

        """
        EnumerateCallback_Proto = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)
        def func(hDevice, pvContext):
            span = TaggedSpan("enumeratecallback closure", self.debug_level >= 2)
            self._EnumerateCallback(hDevice, pvContext)
        return EnumerateCallback_Proto(func)

    def _RegisterPageCallbackClosure(self):
        """
        Returns a pointer to function that calls self._RegisterPageCallback method. This allows class methods to be called from within DirectOutput.dll

        http://stackoverflow.com/questions/7259794/how-can-i-get-methods-to-work-as-callbacks-with-python-ctypes

        """
        PageCallback_Proto = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.wintypes.DWORD, ctypes.c_bool, ctypes.c_void_p)
        def func(hDevice, dwPage, bActivated, pvContext):
            span = TaggedSpan("registerpage closure", self.debug_level >= 2)
            self._RegisterPageCallback(hDevice, dwPage, bActivated, pvContext)
        return PageCallback_Proto(func)

    def _RegisterSoftButtonCallbackClosure(self):
        """
        Returns a pointer to function that calls self._RegisterSoftButtonCallback method. This allows class methods to be called from within DirectOutput.dll

        http://stackoverflow.com/questions/7259794/how-can-i-get-methods-to-work-as-callbacks-with-python-ctypes

        """
        SoftButtonCallback_Proto = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.wintypes.DWORD, ctypes.c_void_p)
        def func(hDevice, dwButtons, pvContext):
            span = TaggedSpan("softbutton closure", self.debug_level >= 2)
            self._RegisterSoftButtonCallback(hDevice, dwButtons, pvContext)
        return SoftButtonCallback_Proto(func)

    def _DeviceCallback(self, hDevice, bAdded, pvContext):
        """
        Internal function to register device handle

        """
        span = TaggedSpan("_devicecallback", self.debug_level >= 2)
        if not bAdded:
            raise NotImplementedError("Received a message that a device went away.")
        if self.device_handle and self.device_handle != hDevice:
            raise IndexError("Too many Saitek devices present")
        self.device_handle = hDevice

    def _EnumerateCallback(self, hDevice, pvContext):
        """
        Internal function to process a device enumeration

        """
        span = TaggedSpan("_enumeratecallback", self.debug_level >= 2)
        self._DeviceCallback(hDevice, True, pvContext)

    def _RegisterPageCallback(self, hDevice, dwPage, bActivated, pvContext):
        """
        Method called when page changes. Calls self.RegisterPageCallback to hide hDevice and pvContext from end-user

        """
        span = TaggedSpan("_registerpagecallback", self.debug_level >= 2)
        self.RegisterPageCallback(dwPage, bActivated)

    def _RegisterSoftButtonCallback(self, hDevice, dwButtons, pvContext):
        """
        Method called when soft button changes. Calls self.RegisterSoftButtonCallback to hide hDevice and pvContext from end-user. Also hides change of page softbutton and press-up.

        """
        span = TaggedSpan("_registersoftbuttoncallback", self.debug_level >= 2)
        self.RegisterSoftButtonCallback(self.Buttons(dwButtons))

    def RegisterPageCallback(self, page, activated):
        """
        Method called when a page changes. This should be overwritten by inheriting class

        Required Arguments:
        page -- page_id passed to AddPage
        activated -- true if this page has become the active page, false if this page was the active page

        """
        span = TaggedSpan("registerpagecallback", self.debug_level >= 2)

    def RegisterSoftButtonCallback(self, buttons):
        """
        Method called when a soft button changes. This should be overwritten by inheriting class

        Required Arguments:
        buttons - Buttons object representing button state

        """
        span = TaggedSpan("registersoftbuttoncallback", self.debug_level >= 2)

    def AddPage(self, page, name, active):
        """
        Adds a page to the MFD

        Required Arguments:
        page -- page ID to add
        name -- String specifying page name
        active -- True if page is to become the active page, if False this will not change the active page

        """
        span = TaggedSpan("AddPage(%s, %s, %s)" % (str(page), str(name), str(active)), self.debug_level >= 1)
        self.direct_output.AddPage(self.device_handle, page, name, active)

    def RemovePage(self, page):
        """
        Removes a page from the MFD

        Required Arguments:
        page -- page ID to remove

        """
        span = TaggedSpan("RemovePage(%s)" % (str(page)), self.debug_level >= 1)
        result = self.direct_output.RemovePage(self.device_handle, page)
        if result != S_OK:
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
        span = TaggedSpan("SetString(%s, %s, %s)" % (str(page), str(line), str(string)), self.debug_level >= 1)
        result = self.direct_output.SetString(self.device_handle, page, line, string)
        if result != S_OK:
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
        span = TaggedSpan("SetLed(%s, %s, %s)" % (str(page), str(led), str(value)), self.debug_level >= 1)
        result = self.direct_output.SetLed(self.device_handle, page, led, value)
        if result != S_OK:
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
    import time, sys

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
        except:
            #This is used to catch Ctrl+C, calling finish method is *very* important to de-initalize device.
            device.finish()
            sys.exit()
