# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import logging
from dataclasses import dataclass
from typing import Any

from ax.modelbridge.generation_strategy import GenerationStrategy
from ax.service.utils.scheduler_options import SchedulerOptions
from ax.utils.common.base import Base
from ax.utils.common.logger import get_logger
from ax.utils.common.typeutils import not_none


logger: logging.Logger = get_logger("BenchmarkMethod")


@dataclass(frozen=True)
class BenchmarkMethod(Base):
    """Benchmark method, represented in terms of Ax generation strategy (which tells us
    which models to use when) and scheduler options (which tell us extra execution
    information like maximum parallelism, early stopping configuration, etc.).

    Note: If `BenchmarkMethod.scheduler_optionss.total_trials` is less than
    `BenchmarkProblem.num_trials` then only the number of trials specified in the
    former will be run.

    Note: The `generation_strategy` passed in is assumed to be in its "base state",
    as it will be cloned and reset.
    """

    name: str
    generation_strategy: GenerationStrategy
    scheduler_options: SchedulerOptions
    distribute_replications: bool = False

    def __post_init__(self) -> None:
        # We (I think?) in general don't want to fit tracking metrics during our
        # benchmarks. Further, not setting `fit_tracking_metrics=False`causes
        # issues with the ground truth metrics created automatically when running
        # the benchmark - in fact, things will error out deep inside the modeling
        # stack since the model gets both noisy (benchmark) and noiseless (ground
        # truth) observations. While support for this is something we shold add
        # or models, in the context of benchmarking we actually want to avoid
        # fitting the ground truth metrics at all.
        if self.generation_strategy.is_node_based:
            raise NotImplementedError(
                "Node-based generation strategies are not yet supported in benchmarks."
            )

        # Clone the GS so as to not modify the original one in-place below.
        # Note that this assumes that the GS passed in is in it's base state.
        gs_cloned = self.generation_strategy.clone_reset()
        for step in gs_cloned._steps:
            if step.model_kwargs is None:
                step.model_kwargs = {}
            if step.model_kwargs.get("fit_tracking_metrics", True):
                logger.warning(
                    "Setting `fit_tracking_metrics` in a GenerationStep to False.",
                )
                not_none(step.model_kwargs)["fit_tracking_metrics"] = False

        # hack around not being able to update frozen attribute of a dataclass
        _assign_frozen_attr(self, name="generation_strategy", value=gs_cloned)


def get_sequential_optimization_scheduler_options(
    timeout_hours: int = 4,
) -> SchedulerOptions:
    """The typical SchedulerOptions used in benchmarking.

    Args:
        timeout_hours: The maximum amount of time (in hours) to run each
            benchmark replication. Defaults to 4 hours.
    """
    return SchedulerOptions(
        # Enforce sequential trials by default
        max_pending_trials=1,
        # Do not throttle, as is often necessary when polling real endpoints
        init_seconds_between_polls=0,
        min_seconds_before_poll=0,
        timeout_hours=timeout_hours,
    )


def _assign_frozen_attr(obj: Any, name: str, value: Any) -> None:  # pyre-ignore [2]
    """Assign a new value to an attribute of a frozen dataclass.
    This is an ugly hack and shouldn't be used broadly.
    """
    object.__setattr__(obj, name, value)
