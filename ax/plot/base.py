#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import enum
import json
from typing import Any, NamedTuple

from ax.core.types import TParameterization
from ax.utils.common.serialization import named_tuple_to_dict
from plotly import utils


# Constants used for numerous plots
CI_OPACITY = 0.4
DECIMALS = 3
Z = 1.96


@enum.unique
class AxPlotTypes(enum.Enum):
    """Enum of Ax plot types."""

    CONTOUR = 0
    GENERIC = 1
    SLICE = 2
    INTERACT_CONTOUR = 3
    BANDIT_ROLLOUT = 4
    INTERACT_SLICE = 5
    HTML = 6


# Configuration for all plots
class _AxPlotConfigBase(NamedTuple):
    data: dict[str, Any]
    plot_type: enum.Enum


class AxPlotConfig(_AxPlotConfigBase):
    """Config for plots"""

    def __new__(cls, data: dict[str, Any], plot_type: enum.Enum) -> "AxPlotConfig":
        # Convert data to json-encodable form (strips out NamedTuple and numpy
        # array). This is a lossy conversion.
        dict_data = json.loads(
            json.dumps(named_tuple_to_dict(data), cls=utils.PlotlyJSONEncoder)
        )
        # pyre-fixme[7]: Expected `AxPlotConfig` but got `NamedTuple`.
        return super().__new__(cls, dict_data, plot_type)


# Structs for plot data
class PlotInSampleArm(NamedTuple):
    """Struct for in-sample arms (both observed and predicted data)"""

    name: str
    parameters: TParameterization
    y: dict[str, float]
    y_hat: dict[str, float]
    se: dict[str, float]
    se_hat: dict[str, float]
    context_stratum: dict[str, str | float] | None


class PlotOutOfSampleArm(NamedTuple):
    """Struct for out-of-sample arms (only predicted data)"""

    name: str
    parameters: TParameterization
    y_hat: dict[str, float]
    se_hat: dict[str, float]
    context_stratum: dict[str, str | float] | None


class PlotData(NamedTuple):
    """Struct for plot data, including both in-sample and out-of-sample arms"""

    metrics: list[str]
    in_sample: dict[str, PlotInSampleArm]
    out_of_sample: dict[str, dict[str, PlotOutOfSampleArm]] | None
    status_quo_name: str | None


class PlotMetric(NamedTuple):
    """Struct for metric"""

    # @TODO T40555279: metric --> metric_name everywhere in plotting
    metric: str
    pred: bool
    rel: bool
