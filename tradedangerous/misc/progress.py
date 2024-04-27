from rich.progress import (
        Progress as RichProgress,
        BarColumn, DownloadColumn, MofNCompleteColumn, SpinnerColumn, 
        TaskProgressColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn,
        TransferSpeedColumn
)

from typing import Optional


class BarStyle:
    """ Base class for Progress bar style types. """
    def __init__(self, width: int=10, prefix: Optional[str] = None):
        self.columns = [SpinnerColumn()]
        if prefix is not None:
            self.columns += [TextColumn(prefix)]
        self.columns += [BarColumn(bar_width=width)]
        self.columns += [TaskProgressColumn()]
        self.columns += [TimeElapsedColumn()]


class CountingBar(BarStyle):
    """ Creates a progress bar that is counting M/N items to completion. """
    def __init__(self, width: int=10, prefix: Optional[str] = None):
        self.columns = [SpinnerColumn()]
        if prefix is not None:
            self.columns += [TextColumn(prefix)]
        self.columns += [BarColumn(bar_width=width)]
        self.columns += [MofNCompleteColumn()]
        self.columns += [TimeElapsedColumn()]


class DefaultBar(BarStyle):
    """ Creates a simple default progress bar with a percentage and time elapsed. """
    pass


class TransferBar(BarStyle):
    """ Creates a progress bar representing a data transfer, which shows the amount of
        data transferred, speed, and estimated time remaining. """
    def __init__(self, width: int=16, prefix: Optional[str] = None):
        self.columns = (
            SpinnerColumn(),
            TextColumn(prefix),
            BarColumn(bar_width=width),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        )


class Progress:
    """
    Facade around the rich Progress bar system to help transition away from
    TD's original basic progress bar implementation.
    """
    def __init__(self, max_value: float, width: int, start: float = 0, prefix: str = "", *, style: BarStyle = DefaultBar) -> None:
        """
            :param max_value: Last value we can reach (100%).
            :param width:     How wide to make the bar itself.
            :param start:     Override initial value to non-zero.
            :param prefix:    Text to print between the spinner and the bar.
        """
        self.max_value = 0 if max_value is None else max(max_value, start)
        self.value = start
        self.prefix = prefix
        self.width = width
        
        # The 'Progress' itself is a view for displaying the progress of tasks. So we construct it
        # and then create a task for our job.
        self.progress = RichProgress(
            # What fields to display.
            *style(width=self.width, prefix=self.prefix).columns,
            # Hide it once it's finished, update it for us, 4x a second
            transient=True, auto_refresh=True, refresh_per_second=4
        )

        # Now we add an actual task to track progress on.
        self.task = self.progress.add_task("Working...", total=max_value, start=True)
        if self.value:
            self.progress.update(self.task, advance=self.value)

        # And show the task tracker.
        self.progress.start()

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.clear()

    def increment(self, value: float, description: Optional[str] = None, *, postfix: str = "") -> None:
        """
        Increase the progress of the bar by a given amount.
        
        :param value:  How much to increase the progress by.
        :param postfix: [deprecated] text added after the bar
        :param description: If set, replaces the task description.
        """
        if description:
            self.progress.update(self.task, description=description)
        self.value += value              # Update our internal count
        if self.value >= self.max_value:  # Did we go past the end? Increase the end.
            self.max_value += value * 2
            self.progress.update(self.task, total=self.max_value)
        if self.max_value > 0:
            self.progress.update(self.task, completed=self.value)

    def clear(self) -> None:
        """ Remove the current progress bar, if any. """
        if self.task:
            self.progress.remove_task(self.task)
            self.task = None
        if self.progress:
            self.progress.stop()
            self.progress = None
