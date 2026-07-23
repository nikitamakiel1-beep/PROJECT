from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Callable, Sequence


@dataclass(frozen=True)
class Transition:
    state: tuple[float, ...]
    action: int
    reward: float
    next_state: tuple[float, ...]
    done: bool
    permitted: bool = True


class ReplayMemory:
    def __init__(self, capacity=2048, seed=271):
        self.capacity = capacity
        self.items = []
        self.rng = random.Random(seed)

    def append(self, transition):
        if not transition.permitted:
            raise ValueError("unsafe transition cannot enter replay")
        self.items.append(transition)
        if len(self.items) > self.capacity:
            self.items.pop(0)

    def sample(self, size):
        if size > len(self.items):
            raise ValueError("insufficient replay items")
        return self.rng.sample(self.items, size)


class LinearQNetwork:
    def __init__(self, state_size, action_count, seed=277):
        rng = random.Random(seed)
        self.state_size = state_size
        self.action_count = action_count
        self.weights = [[rng.uniform(-0.1, 0.1) for _ in range(action_count)] for _ in range(state_size)]
        self.bias = [0.0] * action_count

    def predict(self, state):
        return [self.bias[action] + sum(float(state[index]) * self.weights[index][action] for index in range(self.state_size)) for action in range(self.action_count)]

    def copy_from(self, other):
        self.weights = [list(row) for row in other.weights]
        self.bias = list(other.bias)


class DQNAgent:
    def __init__(self, state_size, action_count, learning_rate=0.02, gamma=0.95, epsilon=0.15, seed=281):
        self.online = LinearQNetwork(state_size, action_count, seed)
        self.target = LinearQNetwork(state_size, action_count, seed + 1)
        self.target.copy_from(self.online)
        self.action_count = action_count
        self.learning_rate = learning_rate
        self.gamma = gamma
        self.epsilon = epsilon
        self.rng = random.Random(seed + 2)
        self.steps = 0

    def choose_action(self, state, permitted_actions=None):
        permitted = list(permitted_actions if permitted_actions is not None else range(self.action_count))
        if not permitted:
            raise ValueError("no permitted actions")
        if self.rng.random() < self.epsilon:
            return self.rng.choice(permitted)
        q_values = self.online.predict(state)
        return max(permitted, key=lambda action: q_values[action])

    def train_batch(self, transitions: Sequence[Transition], clip=1.0):
        losses = []
        gradients = []
        for transition in transitions:
            current = self.online.predict(transition.state)
            target_next = self.target.predict(transition.next_state)
            target = transition.reward if transition.done else transition.reward + self.gamma * max(target_next)
            error = max(-clip, min(clip, current[transition.action] - target))
            losses.append(error * error)
            gradients.append(error)
            for index, value in enumerate(transition.state):
                self.online.weights[index][transition.action] -= self.learning_rate * error * value
            self.online.bias[transition.action] -= self.learning_rate * error
        self.steps += 1
        if self.steps % 10 == 0:
            self.target.copy_from(self.online)
        return sum(losses) / max(len(losses), 1), max((abs(value) for value in gradients), default=0.0)


class SoftmaxPolicy:
    def __init__(self, state_size, action_count, seed=293):
        rng = random.Random(seed)
        self.state_size = state_size
        self.action_count = action_count
        self.weights = [[rng.uniform(-0.05, 0.05) for _ in range(action_count)] for _ in range(state_size)]

    def probabilities(self, state, permitted_actions=None):
        logits = [sum(state[index] * self.weights[index][action] for index in range(self.state_size)) for action in range(self.action_count)]
        permitted = set(permitted_actions if permitted_actions is not None else range(self.action_count))
        masked = [value if action in permitted else -1e9 for action, value in enumerate(logits)]
        maximum = max(masked)
        exp = [math.exp(max(-40.0, min(40.0, value - maximum))) for value in masked]
        total = sum(exp) or 1.0
        return [value / total for value in exp]


class PolicyGradientAgent:
    def __init__(self, state_size, action_count, learning_rate=0.01, gamma=0.95, entropy_weight=0.01, seed=307):
        self.policy = SoftmaxPolicy(state_size, action_count, seed)
        self.learning_rate = learning_rate
        self.gamma = gamma
        self.entropy_weight = entropy_weight
        self.rng = random.Random(seed + 1)

    def choose_action(self, state, permitted_actions=None):
        probabilities = self.policy.probabilities(state, permitted_actions)
        threshold = self.rng.random()
        cumulative = 0.0
        for action, probability in enumerate(probabilities):
            cumulative += probability
            if threshold <= cumulative:
                return action
        return len(probabilities) - 1

    def update_episode(self, states, actions, rewards, permitted_actions=None, clip=1.0):
        returns = []
        running = 0.0
        for reward in reversed(rewards):
            running = reward + self.gamma * running
            returns.append(running)
        returns.reverse()
        mean = sum(returns) / max(len(returns), 1)
        variance = sum((value - mean) ** 2 for value in returns) / max(len(returns), 1)
        standard = math.sqrt(variance) or 1.0
        normalised = [(value - mean) / standard for value in returns]
        total_loss = 0.0
        for state, action, advantage in zip(states, actions, normalised):
            probabilities = self.policy.probabilities(state, permitted_actions)
            log_probability = math.log(max(probabilities[action], 1e-12))
            entropy = -sum(probability * math.log(max(probability, 1e-12)) for probability in probabilities)
            total_loss += -log_probability * advantage - self.entropy_weight * entropy
            for feature, value in enumerate(state):
                for candidate in range(self.policy.action_count):
                    indicator = 1.0 if candidate == action else 0.0
                    gradient = -(indicator - probabilities[candidate]) * advantage * value
                    gradient = max(-clip, min(clip, gradient))
                    self.policy.weights[feature][candidate] -= self.learning_rate * gradient
        return total_loss / max(len(states), 1)


@dataclass(frozen=True)
class RewardContract:
    positive_outcomes: tuple[str, ...] = ("human_approved", "client_value_verified", "delivery_on_time", "data_quality_improved")
    negative_outcomes: tuple[str, ...] = ("external_action_without_approval", "privacy_violation", "rollback_failure", "invented_claim")
    prohibited_reward_hacking: tuple[str, ...] = ("message_volume", "click_volume", "lead_pressure", "automatic_discount")


class SafeRewardModel:
    def __init__(self, contract=RewardContract()):
        self.contract = contract

    def score(self, outcome_flags):
        flags = set(outcome_flags)
        if flags.intersection(self.contract.negative_outcomes):
            return -10.0
        if flags.intersection(self.contract.prohibited_reward_hacking):
            raise ValueError("reward-hacking metric prohibited")
        return sum(1.0 for item in self.contract.positive_outcomes if item in flags)


class GovernedRLRouter:
    """Routes only reversible internal actions; external actions are masked."""

    ACTIONS = ("research", "prepare_internal_card", "request_human_review", "rebuild_digest", "external_message")
    INTERNAL_ACTIONS = (0, 1, 2, 3)

    def __init__(self, state_size=8):
        self.dqn = DQNAgent(state_size, len(self.ACTIONS))
        self.policy_gradient = PolicyGradientAgent(state_size, len(self.ACTIONS))

    def choose(self, state, mode="dqn"):
        permitted = self.INTERNAL_ACTIONS
        action = self.dqn.choose_action(state, permitted) if mode == "dqn" else self.policy_gradient.choose_action(state, permitted)
        return {"action": self.ACTIONS[action], "action_index": action, "external": False, "human_review": action == 2}
