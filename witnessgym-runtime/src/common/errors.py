from __future__ import annotations

class WitnessGymError(Exception):
    pass

class ConfigError(WitnessGymError):
    pass

class PatternError(WitnessGymError):
    pass

class TransformError(WitnessGymError):
    pass

class InjectError(WitnessGymError):
    pass

class LLMError(WitnessGymError):
    pass

class VerifyError(WitnessGymError):
    pass

class OrchestratorError(WitnessGymError):
    pass
