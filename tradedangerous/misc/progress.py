from rich.progress import (
        Progress as RichProgress,
        TaskID,
        ProgressColumn,
        BarColumn, DownloadColumn, MofNCompleteColumn, SpinnerColumn, 
        TaskProgressColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn,
        TransferSpeedColumn
)
from contextlib import contextmanager

from typing import Iterable, Optional, Union, Type  # noqa


class BarStyle:
    """ Base class for Progress bar style types. """
    def __init__(self, width: int = 10, prefix: Optional[str] = None, *, add_columns: Optional[Iterable[ProgressColumn]]):
        self.columns = [SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(bar_width=width)]
        if add_columns:
            self.columns.extend(add_columns)


class CountingBar(BarStyle):
    """ Creates a progress bar that is counting M/N items to completion. """
    def __init__(self, width: int = 10, prefix: Optional[str] = None):
        my_columns = [MofNCompleteColumn(), TimeElapsedColumn()]
        super().__init__(width, prefix, add_columns=my_columns)


class DefaultBar(BarStyle):
    """ Creates a simple default progress bar with a percentage and time elapsed. """
    def __init__(self, width: int = 10, prefix: Optional[str] = None):
        my_columns = [TaskProgressColumn(), TimeElapsedColumn()]
        super().__init__(width, prefix, add_columns=my_columns)


class LongRunningCountBar(BarStyle):
    """ Creates a progress bar that is counting M/N items to completion with a time-remaining counter """
    def __init__(self, width: int = 10, prefix: Optional[str] = None):
        my_columns = [MofNCompleteColumn(), TimeElapsedColumn(), TimeRemainingColumn()]
        super().__init__(width, prefix, add_columns=my_columns)


class TransferBar(BarStyle):
    """ Creates a progress bar representing a data transfer, which shows the amount of
        data transferred, speed, and estimated time remaining. """
    def __init__(self, width: int = 16, prefix: Optional[str] = None):
        my_columns = [DownloadColumn(), TransferSpeedColumn(), TimeRemainingColumn()]
        super().__init__(width, prefix, add_columns=my_columns)


class Progress:
    """
    Facade around the rich Progress bar system to help transition away from
    TD's original basic progress bar implementation.
    """
    def __init__(self,
                 max_value: Optional[float] = None,
                 width: Optional[int] = None,
                 start: float = 0,
                 prefix: Optional[str] = None,
                 *,
                 style: Optional[Type[BarStyle]] = None,
                 show: bool = True,
                 ) -> None:
        """
            :param max_value: Last value we can reach (100%).
            :param width:     How wide to make the bar itself.
            :param start:     Override initial value to non-zero.
            :param prefix:    Text to print between the spinner and the bar.
            :param style:     Bar-style factory to use for styling.
            :param show:      If False, disables the bar entirely.
        """
        self.show = bool(show)
        if not show:
            return
        
        if style is None:
            style = DefaultBar
        
        self.max_value = 0 if max_value is None else max(max_value, start)
        self.value = start
        self.prefix = prefix or ""
        self.width = width or 25
        # The 'Progress' itself is a view for displaying the progress of tasks. So we construct it
        # and then create a task for our job.
        style_instance = style(width=self.width, prefix=self.prefix)
        self.progress = RichProgress(
            # What fields to display.
            *style_instance.columns,
            # Hide it once it's finished, update it for us, 4x a second
            transient=True, auto_refresh=True, refresh_per_second=5
        )
        
        # Now we add an actual task to track progress on.
        self.task = self.progress.add_task("Working...", total=max_value, start=True)
        if self.value:
            self.progress.update(self.task, advance=self.value)
        
        # And show the task tracker.
        self.progress.start()
    
    def __enter__(self):
        """ Context manager.
            
            Example use:
                
                import time
                import tradedangerous.progress
                
                # Progress(max_value=100, width=32, style=progress.CountingBar)
                with progress.Progress(100, 32, style=progress.CountingBar) as prog:
                    for i in range(100):
                        prog.increment(1)
                        time.sleep(3)
        """
        return self
    
    def __exit__(self, *args, **kwargs):
        self.clear()
    
    def increment(self, value: Optional[float] = None, description: Optional[str] = None, *, progress: Optional[float] = None) -> None:
        """
        Increase the progress of the bar by a given amount.
        
        :param value:  How much to increase the progress by.
        :param description: If set, replaces the task description.
        :param progress: Instead of increasing by value, set the absolute progress to this.
        """
        if not self.show:
            return
        if description:
            self.prefix = description
            self.progress.update(self.task, description=description, refresh=True)
        
        bump = False
        if not value and progress is not None and self.value != progress:
            self.value = progress
            bump = True
        elif value:
            self.value += value              # Update our internal count
            bump = True
        
        if self.value >= self.max_value:  # Did we go past the end? Increase the end.
            self.max_value += value * 2
            self.progress.update(self.task, description=self.prefix, total=self.max_value)
            bump = True
        
        if bump and self.max_value > 0:
            self.progress.update(self.task, description=self.prefix, completed=self.value)
    
    def clear(self) -> None:
        """ Remove the current progress bar, if any. """
        # These two shouldn't happen separately, but incase someone tinkers, test each
        # separately and shut them down.
        if not self.show:
            return
        
        if self.task:
            self.progress.remove_task(self.task)
            self.task = None
        
        if self.progress:
            self.progress.stop()
            self.progress = None
    
    @contextmanager
    def sub_task(self, description: str, max_value: Optional[int] = None, width: int = 25):
        if not self.show:
            yield
            return
        task = self.progress.add_task(description, total=max_value, start=True, width=width)
        try:
            yield task
        finally:
            self.progress.remove_task(task)
    
    def update_task(self, task: TaskID, advance: Union[float, int], description: Optional[str] = None):
        if self.show:
            self.progress.update(task, advance=advance, description=description)
