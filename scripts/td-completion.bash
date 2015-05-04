# bash completition for Trade Dangerous
# see http://kfs.org/td/source

common_opts="--help --debug --detail --quiet --db --cwd --link-ly"
pad_opts="? l l? m m? ml ml? s s? sl sm sm? sml sml?"
ynq_opts="y n ?"

_td_file_list()
{
	COMPREPLY=( $( compgen ${1:-} -- "$2" ) )
	compopt -o filenames 2>/dev/null ||
	compgen -d /non-existing-dir/ > /dev/null
}

_td_common()
{
	local cur prev opts
	COMPREPLY=()
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"

	case ${prev} in
	--cwd|-C)
		_td_file_list -d "$cur"
		return 0
		;;
	--db)
		_td_file_list -f "$cur"
		return 0
		;;
	esac
	return 1
}

_td_buildcache()
{
	local cur prev opts
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"

	case ${prev} in
	--sql|--prices)
		_td_file_list -f "$cur"
		;;
	*)
		_td_common && return 0
		opts="--sql --prices --force --ignore-unknown ${common_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	esac
	return 0
}

_td_buy()
{
	local cur prev opts
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"

	case ${prev} in
	--quantity|--near|--ly|--limit|--gt|--lt)
		# argument required
		;;
	--pad-size|-p)
		opts="${pad_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	*)
		_td_common && return 0
		opts="--quantity --near --ly --limit --pad-size --one-stop --price-sort --supply-sort --gt --lt ${common_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	esac
	return 0
}

_td_export()
{
	local cur prev opts
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"

	case ${prev} in
	--path)
		_td_file_list -d "$cur"
		;;
	--tables|-T)
		# argument required
		;;
	*)
		_td_common && return 0
		opts="--path --tables --all-tables --delete-empty ${common_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	esac
	return 0
}

_td_import()
{
	local cur prev opts
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"

	case ${prev} in
	--plug|-P)
		opts="maddavo"
		COMPREPLY+=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	--url)
		# argument required
		;;
	--option|-O)
		opts="csvs corrections systems stations shipvendors exportcsv csvonly skipdl force use3h use2d usefull help"
		COMPREPLY+=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	*)
		_td_common && return 0
		opts="--plug --url --download --ignore-unknown --option --reset ${common_opts}"
		_td_file_list -f "$cur"
		COMPREPLY+=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	esac
	return 0
}

_td_local()
{
	local cur prev opts
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"

	case ${prev} in
	--ly)
		# argument required
		;;
	--pad-size|-p)
		opts="${pad_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	*)
		_td_common && return 0
		opts="--ly --pad-size --stations --trading --black-market --shipyard --outfitting --rearm --refuel --repair ${common_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	esac
	return 0
}

_td_market()
{
	local cur prev opts
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"

	case ${prev} in
	*)
		_td_common && return 0
		opts="--buying --selling ${common_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	esac
	return 0
}

_td_nav()
{
	local cur prev opts
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"

	case ${prev} in
	--ly-per|--avoid|--via|--refuel-jumps)
		# argument required
		;;
	--pad-size|-p)
		opts="${pad_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	*)
		_td_common && return 0
		opts="--ly-per --avoid --via --stations --refuel-jumps ${common_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	esac
	return 0
}

_td_olddata()
{
	local cur prev opts
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"

	case ${prev} in
	--limit|--near|--ly|--min-age)
		# argument required
		;;
	*)
		_td_common && return 0
		opts="--limit --near --ly --route --min-age ${common_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	esac
	return 0
}

_td_rares()
{
	local cur prev opts
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"

	case ${prev} in
	--ly|--limit|--away|--from)
		# argument required
		;;
	--pad-size|-p)
		opts="${pad_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	*)
		_td_common && return 0
		opts="--ly --limit --price-sort --reverse --pad-size --away --from ${common_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	esac
	return 0
}

_td_run()
{
	local cur prev opts
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"

	case ${prev} in
	--capacity|--credits|--ly-per|--from|-f|--to|-t|--via|--avoid|--hops|--jumps-per|--empty-ly|--start-jumps|-s|--end-jumps|-e|--limit|--age|--max-days-old|-MD|--ls-penalty|--lsp|--margin|--insurance|--routes|--towards|-T|--ls-max|--gain-per-ton|--gpt|--max-gain-per-ton|--mgpt|--max-routes|--prune-score|--prune-hops|--supply|--loop-interval|-li)
		# argument required
		;;
	--pad-size|-p)
		opts="${pad_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	*)
		_td_common && return 0
		opts="--capacity --credits --ly-per --from --to --via --avoid --hops --jumps-per --empty-ly --start-jumps --end-jumps --limit --age --max-days-old --ls-penalty --unique --margin --insurance --routes --checklist --x52-pro --towards --loop --direct --pad-size --black-market --ls-max --gain-per-ton --gpt --max-gain-per-ton --mgpt --max-routes --prune-score --prune-hops --progress --supply --summary --loop-interval --shorten ${common_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	esac
	return 0
}

_td_sell()
{
	local cur prev opts
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"

	case ${prev} in
	--near|--ly-per|--limit|--gt|--lt)
		# argument required
		;;
	--pad-size|-p)
		opts="${pad_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	*)
		_td_common && return 0
		opts="--near --ly-per --limit --price-sort --pad-size --gt --lt ${common_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	esac
	return 0
}

_td_shipvendor()
{
	local cur prev opts
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"

	case ${prev} in
	*)
		_td_common && return 0
		opts="--remove --add --name-sort --no-export ${common_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	esac
	return 0
}

_td_station()
{
	local cur prev opts
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"

	case ${prev} in
	--ls-from-star|--confirm)
		# argument required
		;;
	--black-market|--bm|--market|--shipyard|--outfitting|--rearm|--arm|--refuel|--repair)
		opts="${ynq_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	--pad-size)
		opts="${pad_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	*)
		_td_common && return 0
		opts="--ls-from-star --black-market --market --shipyard --pad-size --outfitting --rearm --refuel --repair --confirm --add --remove --update --no-export ${common_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	esac
	return 0
}

_td_trade()
{
	local cur prev opts
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"

	case ${prev} in
	*)
		_td_common && return 0
		opts="${common_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	esac
	return 0
}

_td_update()
{
	local cur prev opts
	cur="${COMP_WORDS[COMP_CWORD]}"
	prev="${COMP_WORDS[COMP_CWORD-1]}"

	case ${prev} in
	--height|-H|--window-x|-wx|--window-y|-wy|--editor)
		# argument required
		;;
	*)
		_td_common && return 0
		opts="--timestamps --all --use-demand --force-na --height --front --window-x --window-y --gui --editor --sublime --notepad --npp --vim ${common_opts}"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	esac
	return 0
}

_td_main()
{
	local cur prev opts
	COMPREPLY=()
	cur="${COMP_WORDS[COMP_CWORD]}"
	first="${COMP_WORDS[1]}"

	case ${first} in
	buildcache)
		_td_buildcache
		;;
	buy)
		_td_buy
		;;
	export)
		_td_export
		;;
	import)
		_td_import
		;;
	local)
		_td_local
		;;
	market)
		_td_market
		;;
	nav)
		_td_nav
		;;
	olddata)
		_td_olddata
		;;
	rares)
		_td_rares
		;;
	run)
		_td_run
		;;
	sell)
		_td_sell
		;;
	shipvendor)
		_td_shipvendor
		;;
	station)
		_td_station
		;;
	trade)
		_td_trade
		;;
	update)
		_td_update
		;;
	*)
		opts="buildcache buy export import local market nav olddata rares run sell shipvendor station trade update"
		COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
	esac
	return 0
}
complete -X '*__pycache__' -F _td_main   trade.py
complete -X '*__pycache__' -F _td_buy    tdbuyfrom
complete -X '*__pycache__' -F _td_import tdimad
complete -X '*__pycache__' -F _td_local  tdloc
complete -X '*__pycache__' -F _td_nav    tdnav
complete -X '*__pycache__' -F _td_run    tdrun
complete -X '*__pycache__' -F _td_update tdupd
