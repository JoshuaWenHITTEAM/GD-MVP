#
#  Created by Joshua Wen on 2023/03/20.
#  Copyright © 2023 Joshua Wen. All rights reserved.
#
import random
import time
import shutil
import json
from pathlib import Path
from loguru import logger
from thop import profile

import gymnasium as gym
import numpy as np
import torch
import torch.nn.functional as F
import torch.optim as optim
from stable_baselines3.common.buffers import ReplayBuffer
from torch.utils.tensorboard import SummaryWriter

from DQNv2.dqn_core import make_env, QNetwork, linear_schedule, QNetworkLN


def _get_episode_info(infos, idx=0):
    episode = infos.get("episode")
    if not isinstance(episode, dict):
        return None
    episode_valid = infos.get("_episode")
    if episode_valid is not None and not bool(episode_valid[idx]):
        return None

    result = {}
    for key, value in episode.items():
        if key.startswith("_"):
            continue
        if isinstance(value, np.ndarray):
            result[key] = value[idx].item() if value.dtype != object else value[idx]
        else:
            result[key] = value
    return result


def save_checkpoint(state, is_best, filename='checkpoint.pth'):
    """Save checkpoint model to disk

        state -- checkpoint state: model weight and other info
                 binding by user
        is_best -- if the checkpoint is the best. If it is, then
                   save as a best model
    """
    torch.save(state, filename)
    if is_best:
        shutil.copyfile(filename, 'model_best.pth')


def load_checkpoint(filename, model):
    """Load previous checkpoint model

       filename -- model file name
       model -- DQN model
    """
    try:
        checkpoint = torch.load(filename)
    except:
        # load weight saved on gpy device to cpu device
        # see https://discuss.pytorch.org/t/on-a-cpu-device-how-to-load-checkpoint-saved-on-gpu-device/349/3
        checkpoint = torch.load(filename, map_location=lambda storage, loc: storage)
    episode = checkpoint['episode']
    epsilon = checkpoint['epsilon']
    print('pretrained episode = {}'.format(episode))
    print('pretrained epsilon = {}'.format(epsilon))
    model.load_state_dict(checkpoint['state_dict'])
    # time_step = checkpoint.get('best_time_step', None)
    # if time_step is not None:
    #     time_step = checkpoint('time_step')
    # print('pretrained time step = {}'.format(time_step))
    # return episode, epsilon, time_step
    return episode, epsilon


def train_dqn(args):
    run_name = f"{args.modal.lower()}_{args.env_id}__{args.exp_name}__train__{args.seed}__{int(time.time())}"
    run_dir = Path("runs") / run_name
    progress_log_interval = 1
    reward_log_interval = 5
    monitor_log_interval = max(20, int(args.train_frequency))
    loguru_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    logger.add(str(run_dir / "log.txt"), format=loguru_format, level="INFO", enqueue=False)
    logger.info(f"########## Setting ##########")
    args_dict = args.__dict__
    for each_arg, value in args_dict.items():
        logger.info(f"{each_arg}: {value}")
    logger.info(f"########## Start Training ##########")
    logger.info(
        "[TRAIN_RUN] {}",
        json.dumps(
            {
                "run_name": run_name,
                "run_dir": str(run_dir.resolve()),
                "log_file": str((run_dir / "log.txt").resolve()),
                "task": args.env_id,
                "total_timesteps": int(args.total_timesteps),
            },
            ensure_ascii=False,
        ),
    )
    if args.track:
        import wandb

        wandb.init(
            project=args.wandb_project_name,
            entity=args.wandb_entity,
            sync_tensorboard=True,
            config=vars(args),
            name=run_name,
            monitor_gym=True,
            save_code=True,
        )
    writer = SummaryWriter(f"runs/{run_name}")
    writer.add_text(
        "hyperparameters",
        "|param|value|\n|-|-|\n%s" % ("\n".join([f"|{key}|{value}|" for key, value in vars(args).items()])),
    )

    # TRY NOT TO MODIFY: seeding
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.backends.cudnn.deterministic = args.torch_deterministic

    device = torch.device("cuda" if torch.cuda.is_available() and args.cuda else "cpu")

    # env setup
    env_kwargs = {
        "dataset_root": getattr(args, "dataset_root", None),
        "results_root": getattr(args, "results_root", None),
        "split": getattr(args, "split", "test"),
        "models": getattr(args, "models", None),
        "output_root": getattr(args, "output_root", None),
    }
    envs = gym.vector.SyncVectorEnv(
        [make_env(args.env_id, args.modal, args.seed, 0, args.capture_video, run_name, args.use_docker, args.test_mode, env_kwargs)]
    )
    assert isinstance(envs.single_action_space, gym.spaces.Discrete), "only discrete action space is supported"

    # q_network = QNetwork(envs).to(device)
    # q_network = QNetwork(envs, args.num_layers).to(device)
    q_network = QNetworkLN(envs, args.num_layers).to(device)
    optimizer = optim.Adam(q_network.parameters(), lr=float(args.learning_rate))
    # target_network = QNetwork(envs).to(device)
    # target_network = QNetwork(envs, args.num_layers).to(device)
    target_network = QNetworkLN(envs, args.num_layers).to(device)
    target_network.load_state_dict(q_network.state_dict())

    rb = ReplayBuffer(
        args.buffer_size,
        envs.single_observation_space,
        envs.single_action_space,
        device,
        optimize_memory_usage=True,
        handle_timeout_termination=False,
    )
    start_time = time.time()

    # TRY NOT TO MODIFY: start the game
    obs, _ = envs.reset()
    f = np.array([0])
    r_dis = 0.0
    for global_step in range(args.total_timesteps):
        current_lr = float(optimizer.param_groups[0]["lr"])
        # ALGO LOGIC: put action logic here
        epsilon = linear_schedule(args.start_e, args.end_e, args.exploration_fraction * args.total_timesteps,
                                  global_step)
        if global_step % progress_log_interval == 0:
            logger.info(
                "[TRAIN_PROGRESS] {}",
                json.dumps(
                    {
                        "global_step": int(global_step),
                        "total_timesteps": int(args.total_timesteps),
                        "progress": float((global_step + 1) / max(args.total_timesteps, 1)),
                        "epsilon": float(epsilon),
                        "learning_rate": current_lr,
                    },
                    ensure_ascii=False,
                ),
            )
        # if random.random() < epsilon:
        #     actions = np.array([envs.single_action_space.sample() for _ in range(envs.num_envs)])
        # else:
        #     q_values = q_network(torch.Tensor(obs).to(device))
        #     actions = torch.argmax(q_values, dim=1).cpu().numpy()

        if global_step > args.learning_starts:
            if random.random() < epsilon:
                actions = np.array([envs.single_action_space.sample() for _ in range(envs.num_envs)])
            else:
                q_values = q_network(torch.Tensor(obs).to(device))
                actions = torch.argmax(q_values, dim=1).cpu().numpy()
        else:
            actions = f
            # actions = torch.argmax(torch.Tensor(obs).to(device), dim=1).cpu().numpy()
            # print(obs)
            # print(actions)
            # print("######################")

        # TRY NOT TO MODIFY: execute the game and log data.
        next_obs, rewards, terminateds, truncateds, infos = envs.step(actions)
        dones = np.logical_or(terminateds, truncateds)

        # TRY NOT TO MODIFY: record rewards for plotting purposes
        episode_info = _get_episode_info(infos)
        if episode_info is not None:
            r_dis += episode_info["r"]
            logger.info(
                f"global_step={global_step}, episodic_state={episode_info['n']}, "
                f"episodic_action={episode_info['a']}, episodic_return={episode_info['r']}"
            )
            if global_step % reward_log_interval == 0:
                logger.info(
                    "[TRAIN_METRICS] {}",
                    json.dumps(
                        {
                            "global_step": int(global_step),
                            "reward": float(episode_info["r"]),
                            "reward_total": float(r_dis),
                            "epsilon": float(epsilon),
                            "learning_rate": current_lr,
                            "action": int(episode_info["a"]),
                            "state": episode_info["n"],
                        },
                        ensure_ascii=False,
                    ),
                )
            writer.add_scalar("charts/episodic_action", episode_info["a"], global_step)
            writer.add_scalar("charts/episodic_return", r_dis, global_step)
            writer.add_scalar("charts/episodic_length", episode_info["l"], global_step)
            writer.add_scalar("charts/epsilon", epsilon, global_step)
        if episode_info is not None:
            pass

        # TRY NOT TO MODIFY: save data to reply buffer; handle `terminal_observation`
        real_next_obs = next_obs.copy()
        for idx, d in enumerate(dones):
            if d:
                final_obs = infos.get("final_observation")
                final_obs_mask = infos.get("_final_observation")
                if final_obs is not None and final_obs_mask is not None and bool(final_obs_mask[idx]):
                    real_next_obs[idx] = final_obs[idx]
        rb.add(obs, real_next_obs, actions, rewards, dones, infos)
        # print(infos)

        # TRY NOT TO MODIFY: CRUCIAL step easy to overlook
        obs = next_obs
        # f = infos[0]["flag"]

        # ALGO LOGIC: training.
        if global_step > args.learning_starts and global_step % args.train_frequency == 0:
            data = rb.sample(args.batch_size)
            with torch.no_grad():
                target_max, _ = target_network(data.next_observations).max(dim=1)
                td_target = data.rewards.flatten() + args.gamma * target_max * (1 - data.dones.flatten())
            old_val = q_network(data.observations).gather(1, data.actions).squeeze()
            loss = F.mse_loss(td_target, old_val)

            if global_step % monitor_log_interval == 0:
                sps = int(global_step / (time.time() - start_time))
                writer.add_scalar("losses/td_loss", loss, global_step)
                writer.add_scalar("losses/q_values", old_val.mean().item(), global_step)
                logger.info(f"SPS:{sps}")
                logger.info(
                    "[TRAIN_MONITOR] {}",
                    json.dumps(
                        {
                            "global_step": int(global_step),
                            "td_loss": float(loss.item()),
                            "q_value": float(old_val.mean().item()),
                            "epsilon": float(epsilon),
                            "learning_rate": current_lr,
                            "sps": sps,
                        },
                        ensure_ascii=False,
                    ),
                )
                # print("SPS:", int(global_step / (time.time() - start_time)))
                writer.add_scalar("charts/SPS", sps, global_step)

            # optimize the model
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            # update the target network
            if global_step % args.target_network_frequency == 0:
                for target_network_param, q_network_param in zip(target_network.parameters(), q_network.parameters()):
                    target_network_param.data.copy_(
                        args.tau * q_network_param.data + (1.0 - args.tau) * target_network_param.data
                    )
                target_network.load_state_dict(q_network.state_dict())

            if global_step % args.save_checkpoints_freq == 0:
                checkpoint_path = run_dir / ("checkpoint_episode_%d.pth" % global_step)
                save_checkpoint({
                    "episode": global_step,
                    "epsilon": epsilon,
                    "state_dict": q_network.state_dict(),
                }, is_best=False, filename=str(checkpoint_path))
                logger.info("checkpoint saved, episode={}".format(global_step))
                logger.info(
                    "[TRAIN_CHECKPOINT] {}",
                    json.dumps(
                        {
                            "global_step": int(global_step),
                            "checkpoint_path": str(checkpoint_path.resolve()),
                        },
                        ensure_ascii=False,
                    ),
                )

    envs.close()
    writer.close()
    logger.info(
        "[TRAIN_COMPLETED] {}",
        json.dumps(
            {
                "run_name": run_name,
                "run_dir": str(run_dir.resolve()),
                "total_timesteps": int(args.total_timesteps),
            },
            ensure_ascii=False,
        ),
    )


def test_dqn(model_filename, args):
    run_name = f"{args.env_id}__{args.exp_name}__test__{args.seed}__{int(time.time())}"
    loguru_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    logger.add(f"runs/{run_name}/log.txt", format=loguru_format, level="INFO", enqueue=False)
    logger.info("loading checkpoints: {}".format(model_filename))

    env_kwargs = {
        "dataset_root": getattr(args, "dataset_root", None),
        "results_root": getattr(args, "results_root", None),
        "split": getattr(args, "split", "test"),
        "models": getattr(args, "models", None),
        "output_root": getattr(args, "output_root", None),
    }
    envs = gym.vector.SyncVectorEnv(
        [make_env(args.env_id, args.modal, args.seed, 0, args.capture_video, run_name, args.use_docker, args.test_mode, env_kwargs)]
    )
    assert isinstance(envs.single_action_space, gym.spaces.Discrete), "only discrete action space is supported"
    device = torch.device("cuda" if torch.cuda.is_available() and args.cuda else "cpu")
    # model = QNetwork(envs).to(device)
    # model = QNetwork(envs, args.num_layers).to(device)
    model = QNetworkLN(envs, args.num_layers).to(device)
    load_checkpoint(model_filename, model)
    input = torch.zeros((1, 3, 256, 256)).to(device)
    flops, params = profile(model, inputs=(input,))
    print("参数量：", params)
    print("FLOPS：", flops)
    epsilon = 0.0
    obs, _ = envs.reset()
    episodic_return = []
    k = 0
    sum_time = 0
    while len(episodic_return) < args.eval_episodes:
        start = time.time()
        if random.random() < epsilon:
            action = np.array([envs.single_action_space.sample() for _ in range(envs.num_envs)])
        else:
            q_values = model(torch.Tensor(obs).to(device))
            action = torch.argmax(q_values, dim=1).cpu().numpy()
        next_obs, rewards, terminateds, truncateds, infos = envs.step(action)
        dones = np.logical_or(terminateds, truncateds)
        end = time.time()
        sum_time += end - start
        if bool(dones[0]):
            break
        episode_info = _get_episode_info(infos)
        if episode_info is not None:
            logger.info(
                f"episodic_state={episode_info['n']}, episodic_action={episode_info['a']}, "
                f"episodic_return={episode_info['r']}"
            )
            episodic_return += [episode_info["r"]]
        obs = next_obs
        k += 1
    print(sum_time)
    print("time: {:1f}ms".format(sum_time / k * 1000))
