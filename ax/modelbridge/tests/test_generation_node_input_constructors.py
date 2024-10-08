# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import inspect
from collections import Counter
from typing import Any, get_type_hints

from ax.core.arm import Arm
from ax.core.generator_run import GeneratorRun
from ax.modelbridge.generation_node import GenerationNode
from ax.modelbridge.generation_node_input_constructors import (
    InputConstructorPurpose,
    NodeInputConstructors,
)
from ax.modelbridge.model_spec import ModelSpec
from ax.modelbridge.registry import Models
from ax.utils.common.testutils import TestCase
from ax.utils.testing.core_stubs import get_branin_experiment


class TestGenerationNodeInputConstructors(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.sobol_model_spec = ModelSpec(
            model_enum=Models.SOBOL,
            model_kwargs={"init_position": 3},
            model_gen_kwargs={"some_gen_kwarg": "some_value"},
        )
        self.sobol_generation_node = GenerationNode(
            node_name="test", model_specs=[self.sobol_model_spec]
        )
        self.experiment = get_branin_experiment(with_completed_trial=True)
        # construct a list of grs that will mock a list of grs that would exist during
        # a gs.gen call. This list has one single arm GR, and one 3-arm GR.
        self.grs = [
            GeneratorRun(arms=[Arm(parameters={"x1": 1, "x2": 5})]),
            GeneratorRun(arms=[Arm(parameters={"x1": 1, "x2": y}) for y in range(3)]),
        ]

    def test_consume_all_n_constructor(self) -> None:
        """Test that the consume_all_n_constructor returns full n."""
        num_to_gen = NodeInputConstructors.ALL_N(
            previous_node=None,
            next_node=self.sobol_generation_node,
            gs_gen_call_kwargs={"n": 5},
        )
        self.assertEqual(num_to_gen, 5)

    def test_repeat_arm_n_constructor(self) -> None:
        """Test that the repeat_arm_n_constructor returns a small percentage of n."""
        small_n = NodeInputConstructors.REPEAT_N(
            previous_node=None,
            next_node=self.sobol_generation_node,
            gs_gen_call_kwargs={"n": 5},
        )
        medium_n = NodeInputConstructors.REPEAT_N(
            previous_node=None,
            next_node=self.sobol_generation_node,
            gs_gen_call_kwargs={"n": 8},
        )
        large_n = NodeInputConstructors.REPEAT_N(
            previous_node=None,
            next_node=self.sobol_generation_node,
            gs_gen_call_kwargs={"n": 11},
        )
        self.assertEqual(small_n, 0)
        self.assertEqual(medium_n, 1)
        self.assertEqual(large_n, 2)

    def test_remaining_n_constructor_expect_1(self) -> None:
        """Test that the remaining_n_constructor returns the remaining n."""
        # should return 1 because 4 arms already exist and 5 are requested
        expect_1 = NodeInputConstructors.REMAINING_N(
            previous_node=None,
            next_node=self.sobol_generation_node,
            gs_gen_call_kwargs={"n": 5, "grs_this_gen": self.grs},
        )
        self.assertEqual(expect_1, 1)

    def test_remaining_n_constructor_expect_0(self) -> None:
        # should return 0 because 4 arms already exist and 4 are requested
        expect_0 = NodeInputConstructors.REMAINING_N(
            previous_node=None,
            next_node=self.sobol_generation_node,
            gs_gen_call_kwargs={"n": 4, "grs_this_gen": self.grs},
        )
        self.assertEqual(expect_0, 0)

    def test_remaining_n_constructor_cap_at_zero(self) -> None:
        # should return 0 because 4 arms already exist and 3 are requested
        # this is a bad state that should never be hit, but ensuring proper
        # handling here feels like a valid edge case
        expect_0 = NodeInputConstructors.REMAINING_N(
            previous_node=None,
            next_node=self.sobol_generation_node,
            gs_gen_call_kwargs={"n": 3, "grs_this_gen": self.grs},
        )
        self.assertEqual(expect_0, 0)

    def test_no_n_provided_error_all_n(self) -> None:
        """Test raise error if n is not specified."""
        with self.assertRaisesRegex(
            NotImplementedError,
            "`consume_all_n` only supports cases where n is specified",
        ):
            _ = NodeInputConstructors.ALL_N(
                previous_node=None,
                next_node=self.sobol_generation_node,
                gs_gen_call_kwargs={},
            )

    def test_no_n_provided_error_repeat_n(self) -> None:
        with self.assertRaisesRegex(
            NotImplementedError,
            " `repeat_arm_n` only supports cases where n is specified",
        ):
            _ = NodeInputConstructors.REPEAT_N(
                previous_node=None,
                next_node=self.sobol_generation_node,
                gs_gen_call_kwargs={},
            )

    def test_no_n_provided_error_remaining_n(self) -> None:
        with self.assertRaisesRegex(
            NotImplementedError, "only supports cases where n is specified"
        ):
            _ = NodeInputConstructors.REMAINING_N(
                previous_node=None,
                next_node=self.sobol_generation_node,
                gs_gen_call_kwargs={},
            )


class TestInstantiationFromNodeInputConstructor(TestCase):
    """Class to test that all node input constructors can be instantiated and are
    being tested."""

    def setUp(self) -> None:
        super().setUp()
        self.constructor_cases = {
            "ALl_N": NodeInputConstructors.ALL_N,
            "REPEAT_N": NodeInputConstructors.REPEAT_N,
            "REMAINING_N": NodeInputConstructors.REMAINING_N,
        }
        self.purpose_cases = {
            "N": InputConstructorPurpose.N,
        }

    def test_all_constructors_have_same_signature(self) -> None:
        """Test that all node input constructors methods have the same signature
        and that the parameters are of the expected types"""
        all_constructors_tested = list(self.constructor_cases.values())
        method_signature = inspect.signature(all_constructors_tested[0])
        for constructor in all_constructors_tested[1:]:
            with self.subTest(constructor=constructor):
                func_parameters = get_type_hints(constructor.__call__)
                self.assertEqual(
                    Counter(list(func_parameters.keys())),
                    Counter(
                        ["previous_node", "next_node", "gs_gen_call_kwargs", "return"]
                    ),
                )
                self.assertEqual(
                    func_parameters["previous_node"], GenerationNode | None
                )
                self.assertEqual(func_parameters["next_node"], GenerationNode)
                # pyre-ignore [16]: Undefined attribute [16]: `dict` has no attribute
                # `__getitem__`.¸
                self.assertEqual(func_parameters["gs_gen_call_kwargs"], dict[str, Any])
                self.assertEqual(method_signature, inspect.signature(constructor))
