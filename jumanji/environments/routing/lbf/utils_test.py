# Copyright 2022 InstaDeep Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import chex
import jax
import jax.numpy as jnp

from jumanji.environments.routing.lbf.constants import DOWN, LEFT, RIGHT, UP
from jumanji.environments.routing.lbf.types import Agent, Food
from jumanji.environments.routing.lbf.utils import (
    eat,
    fix_collisions,
    is_adj,
    move,
    place_agent_on_grid,
    place_food_on_grid,
    slice_around,
)


def test_place_agent_on_grid(agent1: Agent, agents: Agent) -> None:
    grid = jnp.zeros((3, 3))

    expected_agent_1_grid = jnp.array([[0, agent1.level, 0], [0, 0, 0], [0, 0, 0]])
    assert jnp.all(place_agent_on_grid(agent1, grid) == expected_agent_1_grid)

    agent_grids = jax.vmap(place_agent_on_grid, (0, None))(agents, grid)
    expected_grids = jnp.array(
        [
            [[1, 0, 0], [0, 0, 0], [0, 0, 0]],
            expected_agent_1_grid,
            [[0, 0, 0], [2, 0, 0], [0, 0, 0]],
            [[0, 0, 0], [0, 0, 1], [0, 0, 0]],
        ]
    )
    assert jnp.all(agent_grids == expected_grids)


def test_place_food_on_grid(foods: Food) -> None:
    grid = jnp.zeros((3, 3))

    expected_food_grid = jnp.array([[0, 0, 0], [0, 4, 0], [3, 0, 0]])
    food_grid = jnp.sum(jax.vmap(place_food_on_grid, (0, None))(foods, grid), axis=0)
    assert jnp.all(food_grid == expected_food_grid)


def test_move(agent3: Agent, agent1: Agent, agents: Agent, foods: Food) -> None:
    # Agent 1 is at [0, 1] and can move to [0, 0] or [0, 2].
    # But there is a food at [1, 1] so it cannot move there.
    grid_size = 3
    # Move agent 1 to [0, 2]
    agent1_new = move(agent1, RIGHT, foods, agents, grid_size)
    assert jnp.all(agent1_new.position == jnp.array([0, 2]))

    # Try move agent 1 into agent 0.
    agent1_new = move(agent1, LEFT, foods, agents, grid_size)
    assert jnp.all(agent1_new.position == agent1.position)

    # Try move agent 1 into food 0.
    agent1_new = move(agent1, DOWN, foods, agents, grid_size)
    assert jnp.all(agent1_new.position == agent1.position)

    # Try move agent 1 out of bounds.
    agent1_new = move(agent1, UP, foods, agents, grid_size)
    assert jnp.all(agent1_new.position == agent1.position)


def test_is_adj(
    agents: Agent, agent0: Agent, agent1: Agent, agent2: Agent, agent3: Agent
) -> None:
    assert is_adj(agent0, agent1)
    assert is_adj(agent0, agent2)
    assert not is_adj(agent0, agent3)
    assert not is_adj(agent1, agent3)
    assert not is_adj(agent2, agent3)
    assert not is_adj(agent1, agent2)

    # check that vmap also works with is_adj
    expected_adj = jnp.array([False, True, True, False])
    assert jnp.all(jax.vmap(is_adj, (0, None))(agents, agent0) == expected_adj)


def test_eat(agents: Agent, food0: Food, food1: Food) -> None:
    # food 0 can be eaten, food 1 has too high a level for adj agents.
    # set all agent actions to loading
    all_loading_agents = jax.vmap(lambda agent: agent.replace(loading=True))(agents)

    # check that food 0 can be eaten
    new_food0, eaten_food0, adj_agents = eat(all_loading_agents, food0)
    assert new_food0.eaten
    assert eaten_food0
    assert jnp.all(adj_agents == agents.level * jnp.array([0, 1, 1, 1]))

    # check that food 1 cannot be eaten
    new_food1, eaten_food1, adj_agents = eat(all_loading_agents, food1)
    assert not new_food1.eaten
    assert not eaten_food1
    assert jnp.all(adj_agents == agents.level * jnp.array([0, 0, 1, 0]))

    # check that if food is already eaten, it cannot be eaten again
    new_food0, eaten_food0, adj_agents = eat(all_loading_agents, new_food0)
    assert new_food0.eaten
    assert not eaten_food0
    assert jnp.all(adj_agents == agents.level * jnp.array([0, 1, 1, 1]))


def test_flag_duplicates() -> None:
    pass


def test_fix_collisions(agents: Agent) -> None:
    # agents original postions: [[0, 0], [0, 1], [1, 0], [1, 2]]

    # fake moves for agents:
    moved_agents = jax.vmap(Agent)(
        id=agents.id,
        level=agents.level,
        # collision on agent 0 and 3
        position=jnp.array([[0, 0], [0, 2], [2, 0], [0, 2]]),
    )

    # expected postions after collision fix:
    expected_agents = jax.vmap(Agent)(
        id=agents.id,
        level=agents.level,
        # take orig agent for agent 0 and 3
        position=jnp.array([[0, 0], [0, 1], [2, 0], [1, 2]]),
    )

    new_agents = fix_collisions(moved_agents, agents)
    chex.assert_trees_all_equal(new_agents, expected_agents)


def test_slice_around() -> None:
    pos = jnp.array([1, 1])
    fov = 1

    grid = jnp.arange(9).reshape(3, 3)
    grid = jnp.pad(grid, 1, mode="constant", constant_values=-1)

    # expected slice
    expected_slice = jnp.array(
        [
            [0, 1, 2],
            [3, 4, 5],
            [6, 7, 8],
        ]
    )

    # slice around pos
    slice_coords = slice_around(pos, fov)
    view = jax.lax.dynamic_slice(grid, slice_coords, (2 * fov + 1, 2 * fov + 1))

    assert jnp.all(view == expected_slice)

    # slice around pos with fov=2
    fov = 2
    expected_slice = jnp.array(
        [
            [-1, -1, -1, -1, -1],
            [-1, 0, 1, 2, -1],
            [-1, 3, 4, 5, -1],
            [-1, 6, 7, 8, -1],
            [-1, -1, -1, -1, -1],
        ]
    )

    slice_coords = slice_around(pos, fov)
    view = jax.lax.dynamic_slice(grid, slice_coords, (2 * fov + 1, 2 * fov + 1))
    assert jnp.all(view == expected_slice)
