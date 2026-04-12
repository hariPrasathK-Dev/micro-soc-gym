# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
FastAPI + Gradio application for the Micro-SOC Gym Environment.

OpenEnv HTTP API (handled by openenv-core's create_app):
    POST /reset          Start a new episode
    POST /step           Execute an agent action
    GET  /state          Current episode metadata
    GET  /schema         Action / observation JSON schemas
    GET  /health         Liveness probe

Additional endpoint:
    GET  /grade_episode  Post-episode verification score (0.01 - 0.99)

Gradio UI — mounted at /:
    Interactive SOC dashboard. Human-playable demo for judges.
    Served automatically by HuggingFace Spaces on port 7860.
"""

from __future__ import annotations

try:
    from openenv.core.env_server.http_server import create_app
except Exception as exc:
    raise ImportError(
        "openenv-core is required. Run:  uv sync"
    ) from exc

import gradio as gr

from models import MicroSocGymAction, MicroSocGymObservation
from server.micro_soc_gym_environment import MicroSocGymEnvironment
from server.ui import build_ui


# Singleton environment
# Shared between the OpenEnv HTTP API and the Gradio UI.
# One env per server process — consistent with max_concurrent_envs=1.
_env = MicroSocGymEnvironment()

app = create_app(
    lambda: _env,
    MicroSocGymAction,
    MicroSocGymObservation,
    env_name="micro_soc_gym",
    max_concurrent_envs=1,
)


# Extra endpoint: post-episode grading
# Call after /step returns done=True, before the next /reset.
# Returns a float in (0.01, 0.99) based on actual system state.
@app.get("/grade_episode")
def grade_episode() -> dict:
    score = _env.grade_episode(_env.state.scenario)
    return {
        "episode_id":        _env.state.episode_id,
        "scenario":          _env.state.scenario,
        "score":             score,
        "total_reward":      _env.state.total_reward,
        "steps_taken":       _env.state.step_count,
        "threat_neutralised": _env.state.threat_neutralised,
    }


# Gradio UI — mounted at /
_ui = build_ui(_env)
app = gr.mount_gradio_app(app, _ui, path="/")


# Entry point
def main() -> None:
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()