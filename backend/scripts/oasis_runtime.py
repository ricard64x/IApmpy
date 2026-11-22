"""Memory-conscious OASIS environment creation for Fly.io deployments.

OASIS 0.2.5's default Twitter platform selects `twhin-bert`. At the first
non-empty recommendation refresh it loads a local Transformer model through
PyTorch, even if the simulation activates just one agent. That can trigger a
container OOM on a 2 GiB Fly machine.

The built-in random recommender avoids loading *any recommendation model*.
Agent actions still use the remotely configured LLM API, unchanged.
"""
from __future__ import annotations

import os


RECSYS_OPTIONS = frozenset({"random", "twitter", "twhin-bert"})


def action_concurrency() -> int:
    """A bound on concurrent LLM actions; not a cap on agent population."""
    raw = os.environ.get("OASIS_MAX_CONCURRENT_LLM_ACTIONS", "2")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("OASIS_MAX_CONCURRENT_LLM_ACTIONS must be an integer") from exc
    if value < 1 or value > 30:
        raise ValueError("OASIS_MAX_CONCURRENT_LLM_ACTIONS must be between 1 and 30")
    return value


def make_oasis_env(*, agent_graph, platform: str, db_path: str):
    """Build the same OASIS environment with a cheap Twitter recommendation mode.

    Twitter `random` is OASIS's built-in lightweight alternative. It changes
    exposure/recommendation dynamics; do not compare its opinions directly to
    TwHIN-BERT experiments without documenting the changed algorithm.

    `twitter` uses a MiniLM embedding model, and `twhin-bert` restores the
    heavy upstream default; both are explicit opt-ins for larger machines.
    Reddit continues to use OASIS's built-in ranking, which loads no model.
    """
    import oasis

    semaphore = action_concurrency()
    if platform == "twitter":
        recommender = os.environ.get("OASIS_TWITTER_RECSYS", "random").strip().lower()
        if recommender not in RECSYS_OPTIONS:
            raise ValueError(
                "OASIS_TWITTER_RECSYS must be random, twitter, or twhin-bert"
            )

        if recommender == "twhin-bert":
            # Retain exact upstream behavior only when expressly configured.
            platform_argument = oasis.DefaultPlatformType.TWITTER
        else:
            # Passing a custom platform avoids OASIS's hard-coded TwHIN-BERT.
            # The channel is owned by the platform and reused by the OasisEnv.
            from oasis.social_platform.channel import Channel

            platform_argument = oasis.Platform(
                db_path=db_path,
                channel=Channel(),
                recsys_type=recommender,
                refresh_rec_post_count=2,
                max_rec_post_len=2,
                following_post_count=3,
            )
    elif platform == "reddit":
        recommender = "reddit"
        platform_argument = oasis.DefaultPlatformType.REDDIT
    else:
        raise ValueError("platform must be 'twitter' or 'reddit'")

    print(
        f"[OASIS] {platform}: recsys={recommender}, "
        f"max_concurrent_llm_actions={semaphore}",
        flush=True,
    )
    return oasis.make(
        agent_graph=agent_graph,
        platform=platform_argument,
        database_path=db_path,
        semaphore=semaphore,
    )
