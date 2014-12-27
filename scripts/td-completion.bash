# bash completition for Trade Dangerous
# see http://kfs.org/td/source

common_opts="-h --help --debug -w --detail -v --quiet -q --db --cwd -C --link-ly -L"

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
		opts="--sql --prices -f --force --ignore-unknown -i ${common_opts}"
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
	--quantity|--near|--ly-per|--limit)
		# argument required
		;;
	*)
		_td_common && return 0
		opts="--quantity --near --ly-per --limit --ages --price-sort -P --stock-sort -S ${common_opts}"
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
		opts="--path --tables -T --all-tables --delete-empty ${common_opts}"
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
		opts="buildcache syscsv stncsv skipdl force"
		COMPREPLY+=( $(compgen -W "${opts}" -- ${cur}) )
		;;
	*)
		_td_common && return 0
		opts="--maddavo --plug --url --download --ignore-unknown -i --option -O ${common_opts}"
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
		opts="--ly --ages ${common_opts}"
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
	--ly-per|--avoid)
		# argument required
		;;
	*)
		_td_common && return 0
		opts="--ly-per --avoid ${common_opts}"
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
	--limit)
		# argument required
		;;
	*)
		_td_common && return 0
		opts="--limit ${common_opts}"
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
	--capacity|--credits|--ly-per|--from|--to|--via|--avoid|--hops|--jumps-per|--empty-ly|--start-jumps|-s|--limit|--max-days-old|-MD|--ls-penalty|--lsp|--margin|--insurance|--routes)
		# argument required
		;;
	*)
		_td_common && return 0
		opts="--capacity --credits --ly-per --from --to --via --avoid --hops --jumps-per --empty-ly --start-jumps -s --limit --max-days-old -MD --ls-penalty --lsp --unique --margin --insurance --routes --checklist --x52-pro ${common_opts}"
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
		opts="--near --ly-per --limit --ages --price-sort -P ${common_opts}"
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
		opts="--timestamps -T --all -A --use-demand -D --force-na -0 --height -H --front -F --window-x -wx --window-y -wy --gui -G --editor --sublime --notepad --npp --vim ${common_opts}"
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
	run)
		_td_run
		;;
	sell)
		_td_sell
		;;
	update)
		_td_update
		;;
	*)
		opts="buildcache buy export import local nav olddata run sell update"
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
