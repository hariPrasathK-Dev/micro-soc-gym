# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
server.ui — Gradio UI package for the Micro-SOC Gym.

Public surface:
    build_ui(env: MicroSocGymEnvironment) -> gr.Blocks
"""

from server.ui.layout import build_ui

__all__ = ["build_ui"]