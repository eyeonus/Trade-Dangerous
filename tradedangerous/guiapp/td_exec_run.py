from __future__ import annotations

from typing import Any, Callable


def build_run_argv(
    *,
    resolved: dict[str, Any],
    context: dict[str, Any],
    effective_capacity: int | None,
    append_option: Callable[[list[str], str, Any], None],
    append_flag: Callable[[list[str], str, Any], None],
) -> list[str]:
    argv = ['tradegui.py', 'run']

    append_option(argv, '--capacity', effective_capacity)
    append_option(argv, '--credits', resolved.get('credits'))
    append_option(argv, '--ly-per', resolved.get('jump_range_full_ly'))
    append_option(argv, '--empty-ly', resolved.get('jump_range_empty_ly'))
    append_option(argv, '--age', resolved.get('max_data_age_days'))

    append_option(argv, '--from', resolved.get('starting'))
    append_option(argv, '--to', resolved.get('ending'))
    append_option(argv, '--towards', resolved.get('goalSystem'))
    append_option(argv, '--via', resolved.get('via'))
    append_option(argv, '--avoid', resolved.get('avoid'))

    append_flag(argv, '--loop', resolved.get('loop'))
    append_flag(argv, '--direct', resolved.get('direct'))
    append_option(argv, '--hops', resolved.get('hops'))
    append_option(argv, '--jumps-per', resolved.get('maxJumpsPer'))
    append_option(argv, '--start-jumps', resolved.get('startJumps'))
    append_option(argv, '--end-jumps', resolved.get('endJumps'))
    append_flag(argv, '--show-jumps', resolved.get('showJumps'))

    append_option(argv, '--limit', resolved.get('limit'))
    append_option(argv, '--pad-size', resolved.get('padSize'))
    append_flag(argv, '--no-planet', resolved.get('noPlanet'))
    append_option(argv, '--planetary', resolved.get('planetary'))
    append_option(argv, '--fleet-carrier', resolved.get('fleet'))
    append_option(argv, '--odyssey', resolved.get('odyssey'))
    append_flag(argv, '--black-market', resolved.get('blackMarket'))

    append_option(argv, '--ls-penalty', resolved.get('lsPenalty'))
    append_option(argv, '--ls-max', resolved.get('maxLs'))
    append_option(argv, '--gain-per-ton', resolved.get('minGainPerTon'))
    append_option(argv, '--max-gain-per-ton', resolved.get('maxGainPerTon'))

    append_flag(argv, '--unique', resolved.get('unique'))
    append_option(argv, '--loop-interval', resolved.get('loopInt'))
    append_option(argv, '--margin', resolved.get('margin'))
    append_option(argv, '--insurance', resolved.get('insurance'))

    append_option(argv, '--routes', resolved.get('routes'))
    append_option(argv, '--max-routes', resolved.get('maxRoutes'))
    append_flag(argv, '--checklist', resolved.get('checklist'))
    append_flag(argv, '--x52-pro', resolved.get('x52pro'))
    append_option(argv, '--prune-score', resolved.get('pruneScores'))
    append_option(argv, '--prune-hops', resolved.get('pruneHops'))

    append_flag(argv, '--progress', resolved.get('progress'))
    append_option(argv, '--supply', resolved.get('supply'))
    append_option(argv, '--demand', resolved.get('demand'))
    append_flag(argv, '--summary', resolved.get('summary'))
    append_flag(argv, '--shorten', resolved.get('shorten'))
    return argv
