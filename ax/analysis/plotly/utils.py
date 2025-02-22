# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import numpy as np
import torch
from ax.core.experiment import Experiment
from ax.core.objective import MultiObjective, ScalarizedObjective
from ax.core.outcome_constraint import ComparisonOp, OutcomeConstraint
from ax.exceptions.core import UnsupportedError, UserInputError
from ax.modelbridge.base import Adapter
from botorch.utils.probability.utils import compute_log_prob_feas_from_bounds
from numpy.typing import NDArray

# Because normal distributions have long tails, every arm has a non-zero
# probability of violating the constraint. But below a certain threshold, we
# consider probability of violation to be negligible.
MINIMUM_CONTRAINT_VIOLATION_THRESHOLD = 0.01


def get_constraint_violated_probabilities(
    predictions: list[tuple[dict[str, float], dict[str, float]]],
    outcome_constraints: list[OutcomeConstraint],
) -> dict[str, list[float]]:
    """Get the probability that each arm violates the outcome constraints.

    Args:
        predictions: List of predictions for each observation feature
            generated by predict_at_point.  It should include predictions
            for all outcome constraint metrics.
        outcome_constraints: List of outcome constraints to check.

    Returns:
        A dict of probabilities that each arm violates the outcome
        constraint provided, and for "any_constraint_violated" the probability that
        the arm violates *any* outcome constraint provided.
    """
    if len(outcome_constraints) == 0:
        return {"any_constraint_violated": [0.0] * len(predictions)}
    if any(constraint.relative for constraint in outcome_constraints):
        raise UserInputError(
            "`get_constraint_violated_probabilities()` does not support relative "
            "outcome constraints. Use `Derelativize().transform_optimization_config()` "
            "before passing constraints to this method."
        )

    metrics = [constraint.metric.name for constraint in outcome_constraints]
    means = torch.as_tensor(
        [
            [prediction[0][metric_name] for metric_name in metrics]
            for prediction in predictions
        ]
    )
    sigmas = torch.as_tensor(
        [
            [prediction[1][metric_name] for metric_name in metrics]
            for prediction in predictions
        ]
    )
    feasibility_probabilities: dict[str, NDArray] = {}
    for constraint in outcome_constraints:
        if constraint.op == ComparisonOp.GEQ:
            con_lower_inds = torch.tensor([metrics.index(constraint.metric.name)])
            con_lower = torch.tensor([constraint.bound])
            con_upper_inds = torch.as_tensor([])
            con_upper = torch.as_tensor([])
        else:
            con_lower_inds = torch.as_tensor([])
            con_lower = torch.as_tensor([])
            con_upper_inds = torch.tensor([metrics.index(constraint.metric.name)])
            con_upper = torch.tensor([constraint.bound])

        feasibility_probabilities[constraint.metric.name] = (
            compute_log_prob_feas_from_bounds(
                means=means,
                sigmas=sigmas,
                con_lower_inds=con_lower_inds,
                con_upper_inds=con_upper_inds,
                con_lower=con_lower,
                con_upper=con_upper,
                # "both" can also be expressed by 2 separate constraints...
                con_both_inds=torch.as_tensor([]),
                con_both=torch.as_tensor([]),
            )
            .exp()
            .numpy()
        )

    feasibility_probabilities["any_constraint_violated"] = np.prod(
        list(feasibility_probabilities.values()), axis=0
    )

    return {
        metric_name: (1 - feasibility_probabilities[metric_name]).tolist()
        for metric_name in feasibility_probabilities
    }


def format_constraint_violated_probabilities(
    constraints_violated: dict[str, float],
) -> str:
    """Format the constraints violated for the tooltip."""
    max_metric_length = 70
    constraints_violated = {
        k: v
        for k, v in constraints_violated.items()
        if v > MINIMUM_CONTRAINT_VIOLATION_THRESHOLD
    }
    constraints_violated_str = "<br />  ".join(
        [
            (
                f"{k[:max_metric_length]}{'...' if len(k) > max_metric_length else ''}"
                f": {v * 100:.1f}% chance violated"
            )
            for k, v in constraints_violated.items()
        ]
    )
    if len(constraints_violated_str) == 0:
        return "No constraints violated"
    else:
        constraints_violated_str = "<br />  " + constraints_violated_str

    return constraints_violated_str


def is_predictive(model: Adapter) -> bool:
    """Check if a model is predictive.  Basically, we're checking if
    predict() is implemented.

    NOTE: This does not mean it's capable of out of sample prediction.
    """
    try:
        model.predict(observation_features=[])
    except NotImplementedError:
        return False
    except Exception:
        return True
    return True


def select_metric(experiment: Experiment) -> str:
    """Select the most relevant metric to plot from an Experiment."""
    if experiment.optimization_config is None:
        raise ValueError(
            "Cannot infer metric to plot from Experiment without OptimizationConfig"
        )
    objective = experiment.optimization_config.objective
    if isinstance(objective, MultiObjective):
        raise UnsupportedError(
            "Cannot infer metric to plot from MultiObjective, please "
            "specify a metric"
        )
    if isinstance(objective, ScalarizedObjective):
        raise UnsupportedError(
            "Cannot infer metric to plot from ScalarizedObjective, please "
            "specify a metric"
        )
    return experiment.optimization_config.objective.metric.name
