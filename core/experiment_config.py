from dataclasses import dataclass

@dataclass
class ExperimentConfig:
    """
    Configuration flags to toggle experimental features.
    This guarantees isolated A/B evaluations in the research platform.
    """
    enable_mav: bool = False
    enable_dynamic_threshold: bool = True
    enable_ev: bool = False
    enable_new_exit: bool = False
    experiment_id: str | None = None
    benchmark_version: str | None = None

    @classmethod
    def baseline(cls):
        """Standard frozen baseline configuration (Engine A)."""
        return cls(enable_mav=False)

    @classmethod
    def with_mav(cls):
        """Engine configuration with Market Acceptance Validator enabled (Engine B)."""
        return cls(enable_mav=True)
