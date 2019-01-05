import sys

class Progress(object):
    """
    Helper class that describes a simple text-based progress bar.
    """

    def __init__(self, maxValue, width, start=0, prefix=""):
        """
        Arguments:
            maxValue
                Last value we can reach (100%).
            width
                Number of '='s characters for 100%
            start
                Initial value
            prefix
                Something to print infront of the progress bar
        """
        self.start = start
        self.maxValue = maxValue
        self.width = width
        self.value = start
        self.progress = -1
        self.prefix = prefix
        self.textLen = 0
        self.mask = '\r' + self.prefix + "[{{:<{width}}}]".format(width=width)


    def increment(self, value, postfix=""):
        """
        Increment the progress bar's internal counter by 'value',
        and if this changes the progress step, re-draw the bar.

        Attributes:
            value
                The amount to increment the internal counter by
            postfix [optional]
                String or callable to print after the bar

        Returns:
            False if the progress bar did not redraw,
            True if the progress bar was redrawn,
        """
        self.value = min(self.maxValue, self.value + value)
        progress = int(self.width * (self.value - self.start) / self.maxValue)
        if progress == self.progress:
            return False

        if callable(postfix):
            postfixText = postfix(self.value, self.maxValue)
        else:
            postfixText = postfix
        text = self.mask.format("="*progress) + postfixText + " "
        sys.stdout.write(text)
        sys.stdout.flush()

        self.progress = progress
        self.textLen = len(text)

        return True


    def clear(self):
        """
        Remove the current progress bar, if any
        """
        if self.textLen:
            fin = "\r{:{width}}\r".format('', width=self.textLen)
            sys.stdout.write(fin)
            sys.stdout.flush()