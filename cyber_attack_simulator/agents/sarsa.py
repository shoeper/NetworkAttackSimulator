import numpy as np
import time
from cyber_attack_simulator.agents.agent import Agent


class SarsaAgent(Agent):
    """
    An Agent for the Cyber Attack Simulator environment that uses the Sarsa
    method to find an optimal policy

    Supported action-selection methods:
        - Upper-confidence bounds - UCB
        - epsilon-greedy - egreedy
    """
    types = ["UCB", "egreedy"]

    def __init__(self, type="UCB", alpha=0.1, gamma=0.9, max_epsilon=1.0,
                 min_epsilon=0.02, c=1.0):
        """
        Initialize a new Sarsa agent

        Arguments:
            str type : type of Sarsa agent
            float alpha: the value update step-size for the agent
            float gamma: the discount rate
            float max_epsilon : initial max epsilon value (for e-greedy agent)
            float min_epsilon: minimum epsilon value (for e-greedy agent)
            float c: the exploration hyperparameter (used for UCB agent)
        """
        if type not in self.types:
            raise ValueError("type must be in: {0}".format(self.types))
        self.type = type
        self.alpha = alpha
        self.gamma = gamma
        self.max_epsilon = max_epsilon
        self.min_epsilon = min_epsilon
        self.c = c

        # dictionary for storing state-action visits
        self.n_table = dict()
        self.q_table = dict()

    def train(self, env, num_episodes=100, max_steps=100, verbose=False):
        if verbose:
            print("Sarsa {0} agent: Starting training for {1} episodes"
                  .format(self.type, num_episodes))

        # stores timesteps, rewards and time taken for each episode
        episode_timesteps = []
        episode_rewards = []
        episode_times = []

        if self.type == "UCB":
            param = self.c
        else:
            param = self.max_epsilon

        for e in range(num_episodes):
            start_time = time.time()
            timesteps, reward = self._run_episode(env, max_steps, param)
            ep_time = time.time() - start_time

            # slowly decrease exploration
            if self.type == "egreedy":
                param = self._epsilon_decay(num_episodes, e)

            episode_rewards.append(reward)
            episode_timesteps.append(timesteps)
            episode_times.append(ep_time)
            if verbose:
                self.report_progress(e, num_episodes / 10, episode_timesteps)

        if verbose:
            print("{0} agent: Training complete after {0} episodes"
                  .format(self.type, e))
        return episode_timesteps, episode_rewards, episode_times

    def _run_episode(self, env, max_steps, param):
        """
        Train the agent for a single episode.

        Arguments:
            CyberAttackSimulatorEnv env : the environment
            int max_steps : max number of steps to run episode for
            float param : the action selection hyperparameter value for agent

        Returns:
            int ep_timesteps : number of timesteps taken for epidode
            int ep_reward : reward achieved for episode
            float ep_time : time taken for episode
        """
        a_space = env.action_space
        s = env.reset()
        a = self._choose_action(s, a_space, param)
        ep_reward = 0
        ep_timesteps = 0
        for _ in range(max_steps):
            # increment state-action pair visit count
            self._n(s, a_space)[a] += 1
            result = env.step(a_space[a])
            new_s, reward, done, _ = result
            new_a = self._choose_action(new_s, a_space, param)
            self._q_update(s, a, new_s, new_a, reward, a_space)
            s = new_s
            a = new_a
            ep_reward += reward
            ep_timesteps += 1
            if done:
                break
        return ep_timesteps, ep_reward

    def _choose_action(self, state, action_space, param=0.0):
        """
        Choose action to take from given state using agent defined action
        selection. If hyperparameter not provided then defaults to
        greedy policy.

        Arguments:
            State state : the state to choose action for
            list action_space : list of possible actions for state
            float param : the action selection hyperparameter

        Returns:
            int action : index of chosen action to take
        """
        if self.type == "UCB":
            return self._choose_action_ucb(state, action_space, param)
        else:
            return self._choose_action_egreedy(state, action_space, param)

    def _choose_action_egreedy(self, state, action_space, epsilon=0.0):
        """
        Choose action to take from given state using epsilon-greedy policy
        If epsilon not provided then defaults to greedy policy

        Arguments:
            State state : the state to choose action for
            list action_space : list of possible actions for state
            float epsilon : random action choice hyperparameter

        Returns:
            int action : index of chosen action to take
        """
        if np.random.uniform(0, 1) < epsilon:
            return np.random.randint(0, len(action_space))
        else:
            return np.argmax(self._q(state, action_space))

    def _choose_action_ucb(self, state, action_space, c=0.0):
        """
        Choose action to take from given state using Upper-Confidence-Bound
        action selection. If c hyperparameter not provided then defaults to
        greedy policy.

        Arguments:
            State state : the state to choose action for
            list action_space : list of possible actions for state
            float c : the exploration hyperparameter

        Returns:
            int action : index of chosen action to take
        """
        n_state_action = self._n(state, action_space)
        if np.any(n_state_action == 0):
            # if any state-action pair has not been visited, choose action
            return np.argwhere(n_state_action == 0).flatten()[0]
        log_state_visits = np.log(np.sum(n_state_action))
        bonuses = c * np.sqrt(2 * (log_state_visits / n_state_action))

        q_values = self._q(state, action_space)
        adj_q_values = q_values + bonuses
        return np.argmax(adj_q_values)

    def _q_update(self, s, a, s_new, a_new, r, action_space):
        """
        Update state-action action value using Sarsa update

        Arguments:
            State s: current state
            int a: current action
            State s_new: next state
            int a_new: next action
            float r: reward from performing a in s (current step)
            list action_space : list of possible actions for state
        """
        current_q = self._q(s, action_space, a)
        new_q = self._q(s_new, action_space, a_new)
        td_error = r + self.gamma * new_q - current_q
        self._q(s, action_space)[a] = current_q + self.alpha * td_error

    def _q(self, state, action_space, action=None):
        """
        Returns the Q-value for a state-action pair or returns the list of
        Q-values for a state if no action is provided

        Arguments:
            State state : environment state
            list action_space : list of possible actions for state
            int action : index of action performed

        Returns:
            list q_values : list of action values for state
            or
            float q_value : state-action pair value
        """
        if state not in self.q_table:
            self.q_table[state] = np.zeros(len(action_space))

        if action is None:
            return self.q_table[state]
        return self.q_table[state][action]

    def _n(self, state, action_space, action=None):
        """
        Helper method for dealing with state-action pair visit counts

        Arguments:
            State state : environment state
            list action_space : list of possible actions for state
            int action = index of action to take or None

        Returns:
            list n : list of state-action visits to if action=None
            or
            int n : total visits to state-action pair
        """
        if state not in self.n_table:
            self.n_table[state] = np.zeros(len(action_space))
        if action is None:
            return self.n_table[state]
        return self.n_table[state][action]

    def _epsilon_decay(self, num_episodes, e):
        """
        Decay epsilon value.
        """
        step = (self.max_epsilon - self.min_epsilon) / num_episodes
        return self.max_epsilon - (step * e)

    def reset(self):
        self.n_table = dict()
        self.q_table = dict()

    def _choose_greedy_action(self, state, action_space):
        return self._choose_action(state, action_space)

    def __str__(self):
        if self.type == "UCB":
            return ("UCB: alpha={0}, gamma={1}, c={2}"
                    .format(self.alpha, self.gamma, self.c))
        else:
            return ("e-Greedy: alpha={0}, gamma={1}, min-epsilon={2}"
                    .format(self.alpha, self.gamma, self.min_epsilon))