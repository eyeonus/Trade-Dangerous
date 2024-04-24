"""
x52pro.py - DirectOutputDevice for SaitekX52Pro

Version: 0.2
Author: Frazzle
Version: 0.3
Author: Oliver "kfsone" Smith <oliver@kfs.org> 2014

Description: Python class implementing specific functions for Saitek X52 Pro


TODO:
    * Error handling and exceptions
"""

from tradedangerous.mfd.saitek.directoutput import DirectOutputDevice

import sys
import time


class X52Pro(DirectOutputDevice):
    class Page:
        _lines = [ str(), str(), str() ]
        _leds  = dict()
        
        def __init__(self, device, page_id, name, active):
            self.device = device
            self.page_id = page_id
            self.name = name
            self.device.AddPage(self.page_id, name, 1 if active else 0)
            self.active = active
        
        def __del__(self, *args, **kwargs):
            try:
                self.device.RemovePage(self.page_id)
            except AttributeError:
                pass
        
        def __getitem__(self, key):
            return self._lines[key]
        
        def __setitem__(self, key, value):
            self._lines[key] = value
            if self.active:
                self.device.SetString(self.page_id, key, value)
        
        def activate(self):
            if self.active is True:
                return
            self.device.AddPage(self.page_id, self.name, 1)
        
        def refresh(self):
            # Resend strings to the display
            for lineNo, string in enumerate(self._lines):
                self.device.SetString(self.page_id, lineNo, string)
            for led, value in self._leds:
                self.device.SetLed(self.page_id, led, 1 if value else 0)
        
        def set_led(self, led, value):
            self._leds[led] = value
            if self.active:
                self.device.SetLed(self.page_id, led, 1 if value else 0)
        
        def set_led_colour(self, value, led_red, led_green):
            if value == "red":
                self.set_led(led_red, 1)
                self.set_led(led_green, 0)
            elif value == "green":
                self.set_led(led_red, 0)
                self.set_led(led_green, 1)
            elif value == "orange":
                self.set_led(led_red, 1)
                self.set_led(led_green, 1)
            elif value == "off":
                self.set_led(led_red, 0)
                self.set_led(led_green, 0)
        
        def fire(self, value):
            self.set_led(0, value)
        
        def fire_a(self, value):
            self.set_led_colour(value, 1, 2)
        
        def fire_b(self, value):
            self.set_led_colour(value, 3, 4)
        
        def fire_d(self, value):
            self.set_led_colour(value, 5, 6)
        
        def fire_e(self, value):
            self.set_led_colour(value, 7, 8)
        
        def toggle_1_2(self, value):
            self.set_led_colour(value, 9, 10)
        
        def toggle_3_4(self, value):
            self.set_led_colour(value, 11, 12)
        
        def toggle_5_6(self, value):
            self.set_led_colour(value, 13, 14)
        
        def pov_2(self, value):
            self.set_led_colour(value, 15, 16)
        
        def clutch(self, value):
            self.set_led_colour(value, 17, 18)
        
        def throttle_axis(self, value):
            self.set_led(19, value)
    
    pages = {}
    _page_counter = 0
    
    def add_page(self, name, active=True):
        page = self.pages[name] = self.Page(self, self._page_counter, name, active=active)
        self._page_counter += 1
        return page
    
    def remove_page(self, name):
        del self.pages[name]


    def OnPage(self, page_id, activated):
        super().OnPage(page_id, activated)
        for page in self.pages.values():
            if page.page_id == page_id:
                print("Found the page", page_id, activated)
                if activated:
                    page.refresh()
                else:
                    page.active = False
                return


    def OnSoftButton(self, *args, **kwargs):
        super().OnSoftButton(*args, **kwargs)
        print("*** ON SOFT BUTTON")


    def finish(self):
        for page in self.pages:
            del page
        super().finish()


if __name__ == '__main__':
    x52 = X52Pro(debug_level=1)
    print("X52 Connected")
    
    x52.add_page("Page1")
    print("Page1 page added")
    
    x52.pages["Page1"][0] = "Test String"
    try:
        x52.pages["Page1"][5] = "FAIL"
        raise ValueError("Your stick thinks it has 5 lines of MFD, I think it lies.")
    except IndexError:
        print("Your MFD has the correct number of lines of text")
    
    x52.pages["Page1"][1] = "-- Page 1 [0]"
    
    fireToggle = False
    x52.pages["Page1"].fire(fireToggle)
    x52.pages["Page1"].fire_a("amber")
    x52.pages["Page1"].toggle_3_4("red")
    x52.pages["Page1"].throttle_axis(~fireToggle)
    
    print("Adding second page")
    x52.add_page("Page2", active=False)
    x52.pages["Page2"][0] = "Second Page Is Right Here"
    x52.pages["Page2"][1] = "-- Page 2 [1]"
    
    print("Looping")
    
    loopNo = 0
    while True:
        try:
            loopNo += 1
            x52.pages["Page1"][2] = "Loop #" + str(loopNo)
            time.sleep(0.25)
            x52.pages["Page1"].fire_a("red")
            time.sleep(0.25)
            x52.pages["Page1"].fire_a("orange")
            time.sleep(0.25)
            x52.pages["Page1"].fire_a("green")
            time.sleep(0.25)
            x52.pages["Page1"].fire_a("off")
            fireToggle = ~fireToggle
            x52.pages["Page1"].fire(fireToggle)
            x52.pages["Page1"].throttle_axis(~fireToggle)
        except Exception as e:
            print(e)
            x52.finish()
            sys.exit()
