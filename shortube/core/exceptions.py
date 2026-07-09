class ShortubeError(Exception):
    """Base exception for all shortube errors."""


class PipelineError(ShortubeError):
    """Pipeline execution failed."""


class AgentError(ShortubeError):
    """An agent in the pipeline failed."""


class DiscoveryError(ShortubeError):
    """Trend discovery failed."""


class ResearchError(ShortubeError):
    """Research / fact-checking failed."""


class StoryboardError(ShortubeError):
    """Storyboard generation failed."""


class LLMError(ShortubeError):
    """LLM provider call failed."""


class ConfigurationError(ShortubeError):
    """Invalid or missing configuration."""


class CacheError(ShortubeError):
    """Cache operation failed."""