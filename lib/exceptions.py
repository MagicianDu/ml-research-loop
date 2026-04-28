"""ml-research-loop custom exceptions."""


class MLResearchLoopError(Exception):
    """Base class for all ml-research-loop errors."""
    pass


class TaskNotFoundError(MLResearchLoopError):
    """Raised when a task file does not exist."""
    pass


class TaskLockError(MLResearchLoopError):
    """Raised when a task lock cannot be acquired or times out."""
    pass


class TaskProtocolError(MLResearchLoopError):
    """Raised when JSON protocol parsing fails."""
    pass


class ResultNotReadyError(MLResearchLoopError):
    """Raised when result file is not yet available."""
    pass


class BudgetExceededError(MLResearchLoopError):
    """Raised when experiment budget is exhausted."""
    pass


class TrainingFailedError(MLResearchLoopError):
    """Raised when train.py execution fails."""
    pass


class MetricCalculationError(MLResearchLoopError):
    """Raised when metric calculation fails."""
    pass


class SubagentTimeoutError(MLResearchLoopError):
    """Raised when sub-agent execution times out."""
    pass


class SubagentCrashedError(MLResearchLoopError):
    """Raised when sub-agent exits unexpectedly."""
    pass
