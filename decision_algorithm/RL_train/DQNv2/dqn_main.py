import sys
import os
from pathlib import Path
import argparse
import yaml
from types import SimpleNamespace
from setuptools._distutils.util import strtobool

AGENTS_ROOT = Path(__file__).resolve().parent.parent
if str(AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTS_ROOT))

from DQNv2.dqn_misc import train_dqn, test_dqn
import warnings
# 禁用所有警告
warnings.filterwarnings("ignore")

def parser_args():
    # fmt: off
    parser = argparse.ArgumentParser()
    parser.add_argument("--exp-name", type=str, default=os.path.basename(__file__).rstrip(".py"),
                        help="the name of this experiment")
    parser.add_argument("--seed", type=int, default=1,
                        help="seed of the experiment")
    parser.add_argument("--torch-deterministic", type=lambda x: bool(strtobool(x)), default=True, nargs="?", const=True,
                        help="if toggled, `torch.backends.cudnn.deterministic=False`")
    parser.add_argument("--cuda", type=lambda x: bool(strtobool(x)), default=True, nargs="?", const=True,
                        help="if toggled, cuda will be enabled by default")
    parser.add_argument("--track", type=lambda x: bool(strtobool(x)), default=False, nargs="?", const=True,
                        help="if toggled, this experiment will be tracked with Weights and Biases")
    parser.add_argument("--wandb-project-name", type=str, default="cleanRL",
                        help="the wandb's project name")
    parser.add_argument("--wandb-entity", type=str, default=None,
                        help="the entity (team) of wandb's project")
    parser.add_argument("--capture-video", type=lambda x: bool(strtobool(x)), default=False, nargs="?", const=True,
                        help="whether to capture videos of the agent performances (check out `videos` folder)")

    # Algorithm specific arguments
    parser.add_argument("--env-id", type=str, default="CV-RL",
                        help="the id of the environment")
    parser.add_argument("--total-timesteps", type=int, default=500001,
                        help="total timesteps of the experiments")
    parser.add_argument("--learning-rate", type=float, default=2.5e-4,
                        help="the learning rate of the optimizer")
    parser.add_argument("--buffer-size", type=int, default=10000,
                        help="the replay memory buffer size")
    parser.add_argument("--gamma", type=float, default=0.99,
                        help="the discount factor gamma")
    parser.add_argument("--tau", type=float, default=1,
                        help="the target network update rate")
    parser.add_argument("--target-network-frequency", type=int, default=100,
                        help="the timesteps it takes to update the target network")
    parser.add_argument("--batch-size", type=int, default=128,
                        help="the batch size of sample from the reply memory")
    parser.add_argument("--start-e", type=float, default=1,
                        help="the starting epsilon for exploration")
    parser.add_argument("--end-e", type=float, default=0.05,
                        help="the ending epsilon for exploration")
    parser.add_argument("--exploration-fraction", type=float, default=0.5,
                        help="the fraction of `total-timesteps` it takes from start-e to go end-e")
    parser.add_argument("--learning-starts", type=int, default=10000,
                        help="timestep to start learning")
    parser.add_argument("--train-frequency", type=int, default=10,
                        help="the frequency of training")
    parser.add_argument("--save_checkpoints_freq", type=int, default=10000,
                        help="the frequency of checkpoint saving")
    parser.add_argument("--num_layers", type=int, default=18,
                        help="the number of ResNet layers: 18, 34, 50, 101, 152")
    parser.add_argument("--eval_episodes", type=int, default=1000,
                        help="")
    args = parser.parse_args()
    # fmt: on
    return args


def load_config(cfg_path):
    with open(cfg_path, "r") as cfg:
        cfg_dict = yaml.safe_load(cfg)
        return SimpleNamespace(**cfg_dict)

def dqn_train_start(cfg_path):
    args = load_config(cfg_path)
    train_dqn(args)

def dqn_test_start(model_filename_path, cfg_path):
    args = load_config(cfg_path)
    test_dqn(model_filename_path, args)


def cli_args():
    parser = argparse.ArgumentParser(description="DQNv2 runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_parser = subparsers.add_parser("train", help="Run DQN training from a yaml config")
    train_parser.add_argument("--config", required=True, help="Path to yaml config")

    test_parser = subparsers.add_parser("test", help="Run DQN evaluation from a yaml config")
    test_parser.add_argument("--config", required=True, help="Path to yaml config")
    test_parser.add_argument("--model", required=True, help="Path to checkpoint model")

    return parser.parse_args()


if __name__ == "__main__":
    args = cli_args()
    if args.command == "train":
        dqn_train_start(args.config)
    elif args.command == "test":
        dqn_test_start(args.model, args.config)
