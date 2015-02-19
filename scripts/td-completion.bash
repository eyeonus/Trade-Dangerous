# bash completition for Trade Dangerous
# see http://kfs.org/td/source

common_opts="--help --debug --detail --quiet --db --cwd --link-ly"

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
	--quantity|--near|--ly|--limit)
		# argument required
		;;
	*)
		_td_common && return 0
		opts="--quantity --near --ly --limit --price-sort --stock-sort ${common_opts}"
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
	--plug)
		opts="maddavo"
		COMPREPLY+=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	--url)
		# argument required
		;;
	--option|-O)
		opts="systems stations exportcsv skipdl force use3h use2d usefull"
		COMPREPLY+=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	*)
		_td_common && return 0
		opts="--plug --url --download --ignore-unknown --option ${common_opts}"
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
	*)
		_td_common && return 0
		opts="--ly ${common_opts}"
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
	--ly-per|--avoid|--via)
		# argument required
		;;
	*)
		_td_common && return 0
		opts="--ly-per --avoid --via --stations ${common_opts}"
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
	--limit|--near|--ly)
		# argument required
		;;
	*)
		_td_common && return 0
		opts="--limit --near --ly ${common_opts}"
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
	--ly|--limit)
		# argument required
		;;
	*)
		_td_common && return 0
		opts="--ly --limit --price-sort --reverse ${common_opts}"
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
	--capacity|--credits|--ly-per|--from|--to|--via|--avoid|--hops|--jumps-per|--empty-ly|--start-jumps|-s|--end-jumps|-e|--limit|--max-days-old|-MD|--ls-penalty|--lsp|--margin|--insurance|--routes)
		# argument required
		;;
	*)
		_td_common && return 0
		opts="--capacity --credits --ly-per --from --to --via --avoid --hops --jumps-per --empty-ly --start-jumps --end-jumps --limit --max-days-old --ls-penalty --unique --margin --insurance --routes --checklist --x52-pro ${common_opts}"
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
	--near|--ly-per|--limit)
		# argument required
		;;
	*)
		_td_common && return 0
		opts="--near --ly-per --limit --price-sort ${common_opts}"
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
	--system|--ls-from-star|--black-market|--pad-size|--confirm)
		# argument required
		;;
	*)
		_td_common && return 0
		opts="--system --ls-from-star --black-market --pad-size --confirm --add --remove --update --no-export ${common_opts}"
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
    station)
        _td_station
        ;;
	update)
		_td_update
		;;
	*)
		opts="buildcache buy export import local nav olddata rares run sell station update"
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
