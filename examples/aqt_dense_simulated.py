# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Test compiling and executing a basic AQT MatMul with IREE."""

from collections import namedtuple
import logging

from iree.jax import Program, kernel, like

import jax
import jax.numpy as jnp

logging.basicConfig(level=logging.DEBUG)

activation_example = jnp.arange(30, dtype=jnp.float32).reshape(5, 6) / 10.4

Params = namedtuple("Params", "weights,bias,activation_scale")
params = [
    Params(
        weights=jnp.arange(18, dtype=jnp.float32).reshape(6, 3) * 0.001,
        bias=jnp.arange(3, dtype=jnp.float32) * 10.0,
        activation_scale=jnp.array(5.0),
    ),
    Params(
        weights=jnp.arange(27, dtype=jnp.float32).reshape(3, 9) * 0.01,
        bias=jnp.arange(9, dtype=jnp.float32) * 3.0,
        activation_scale=jnp.array(5.0),
    ),
]


def dense(params, activation):
  precision = 8
  lower_bound = -2**(precision - 1) + 1
  upper_bound = 2**(precision - 1) - 1

  activation_scaled = activation * params.activation_scale
  activation_rounded = jnp.floor(activation_scaled + jnp.array(0.5))
  activation_clipped = jnp.clip(activation_rounded, lower_bound, upper_bound)

  weight_scale = upper_bound / jnp.max(jnp.abs(params.weights))
  weight_scaled = params.weights * weight_scale
  weight_rounded = jnp.floor(weight_scaled + jnp.array(0.5))

  scaled_result = jax.lax.dot(activation_clipped, weight_rounded)
  matmul_result = scaled_result / (params.activation_scale * weight_scale)
  return matmul_result + params.bias[jnp.newaxis, :]


class AqtDenseModule(Program):

  _params = params

  @kernel
  def model(params, activation):
    activation = dense(params[0], activation)
    activation = dense(params[1], activation)
    return activation

  def compute_simulated(self, activation=like(activation_example)):
    return self.model(self._params, activation)


print(Program.get_mlir_module(AqtDenseModule))
